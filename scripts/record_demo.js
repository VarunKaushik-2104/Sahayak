/* Records the demo walkthrough (about 2.5 minutes) against a running server with SEED_DEMO=1 and a fresh database.
   node scripts/record_demo.js http://localhost:8000 demo/raw      -> demo/raw/*.webm   (then ffmpeg to mp4) */
const { chromium } = require(process.env.PLAYWRIGHT_PATH || 'playwright');
const path = require('path');
const BASE = process.argv[2] || 'http://localhost:8000';
const OUT = process.argv[3] || 'demo/raw';
const ARCH = process.argv[4] ? path.resolve(process.argv[4]) : null;
const sleep = ms => new Promise(r => setTimeout(r, ms));

(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 720 }, recordVideo: { dir: OUT, size: { width: 1280, height: 720 } } });
  const page = await ctx.newPage();
  const install = () => page.evaluate(() => {
    if (document.getElementById('cap')) return;
    const st = document.createElement('style');
    st.textContent = `#cap{position:fixed;left:50%;bottom:18px;transform:translateX(-50%);max-width:1000px;background:rgba(20,33,61,.94);color:#fff;font:600 21px/1.35 Inter,Segoe UI,Arial,sans-serif;padding:12px 22px;border-radius:12px;z-index:99999;text-align:center;box-shadow:0 6px 24px rgba(0,0,0,.3);display:none}
      #title{position:fixed;inset:0;background:#2443C4;color:#fff;z-index:100000;display:none;flex-direction:column;align-items:center;justify-content:center;font-family:Inter,Segoe UI,Arial,sans-serif;text-align:center;padding:40px}
      #title h1{font-size:64px;margin:0 0 12px}#title p{font-size:26px;margin:6px 0;max-width:980px;line-height:1.35}`;
    document.head.appendChild(st);
    const c = document.createElement('div'); c.id = 'cap'; document.body.appendChild(c);
    const t = document.createElement('div'); t.id = 'title'; document.body.appendChild(t);
  });
  const cap = async (txt, ms) => { await page.evaluate(t => { const c = document.getElementById('cap'); c.textContent = t; c.style.display = t ? 'block' : 'none'; }, txt); if (ms) await sleep(ms); };
  const title = async (h, lines, ms) => { await page.evaluate(([h, l]) => { const t = document.getElementById('title'); t.innerHTML = `<h1>${h}</h1>` + l.map(x => `<p>${x}</p>`).join(''); t.style.display = 'flex'; }, [h, lines]); await sleep(ms); await page.evaluate(() => { document.getElementById('title').style.display = 'none'; }); };
  const type = async (sel, txt) => { await page.click(sel); await page.type(sel, txt, { delay: 140 }); };
  const goHome = async () => { for (let i = 0; i < 4 && !(await page.locator('[data-a=chapter]').count()); i++) await page.locator('.back').first().click(); };
  const learned = async () => { if (await page.locator('[data-a=learned]').count()) { await sleep(1800); await page.click('[data-a=learned]'); } };
  const scroll = async y => { await page.evaluate(y => window.scrollTo({ top: y, behavior: 'smooth' }), y); await sleep(900); };

  await page.goto(BASE); await page.waitForSelector('#loginform'); await install();
  await title('Sahayak', ['Find the gap behind the gap.', 'Adaptive learning for Classes 6 to 10 · CBSE, ICSE, Telangana', 'Team WIN R · Code Kernel ’26'], 4500);
  await cap('A teacher with 40 students cannot see who is stuck on which basic from an earlier class. Sahayak finds it.', 4500);

  await cap('Student: signs in with a 4-digit PIN on a shared phone. The server issues a signed session.', 1500);
  await type('#f1', '1234'); await sleep(500); await page.click('button[type=submit]'); await page.waitForSelector('.phone'); await sleep(1500);
  await cap('Home: chapters from the Telangana Class 8 book, the teacher’s test date, and how ready the student is.', 4500);

  await cap('A 5-question placement check sets the starting picture on foundation topics.', 2500);
  await page.click('[data-a=diag]');
  for (let i = 0; i < 5; i++) { await sleep(1100); await page.click('[data-a=dans] >> nth=0'); await sleep(700); await page.click('[data-a=dnext]'); }
  await sleep(1500);

  await cap('Open a chapter. Each chapter maps to topics in one shared prerequisite graph.', 3200);
  await page.click('[data-a=chapter] >> nth=0'); await sleep(2500); await scroll(250); await scroll(0);
  await cap('Practise: learn, solve, then a short check. Questions get harder or easier with mastery.', 3000);
  await page.click('[data-a=startp]'); await learned();
  await sleep(1200); await page.click('[data-a=ans] >> nth=0'); await sleep(1800);
  await cap('Every wrong option is tagged with the mistake it shows. Here it points back to a weak basic from Class 6.', 5500);
  await page.click('[data-a=next]'); await sleep(900); await learned(); await sleep(600);
  await page.click('[data-a=ans] >> nth=0'); await sleep(1200); await page.click('[data-a=next]'); await learned();

  await cap('Offline: the engine keeps working. Answers wait in the outbox on the phone.', 2500);
  await page.evaluate(() => document.querySelector('[data-a=net]').click()); await sleep(1000);
  for (let i = 0; i < 2; i++) { await page.click('[data-a=ans] >> nth=0'); await sleep(1100); await page.click('[data-a=next]'); await learned(); }
  await cap('Outbox: items waiting. The server has not seen them yet.', 3500);
  await page.evaluate(() => document.querySelector('[data-a=net]').click());
  await cap('Back online: the outbox sends. The server marks every answer again and returns the authoritative mastery.', 1500);
  await page.waitForFunction(() => /Outbox:\s*0 items/.test(document.body.innerText), null, { timeout: 10000 }); await sleep(3500);

  await goHome(); await cap('Exam preparation: a dated revision plan, weak basics first, a mock the day before.', 1200);
  await page.click('[data-a=nav][data-v=prep]'); await sleep(3500); await scroll(300); await sleep(1500); await scroll(0);
  await cap('Mock test: marked step by step, because examiners give marks for each step.', 2500);
  await page.click('[data-a=mock]');
  for (let i = 0; i < 12 && (await page.locator('[data-a=mans]').count()); i++) { await sleep(900); await page.click('[data-a=mans] >> nth=0'); }
  await page.waitForSelector('.rlist'); await sleep(2500); await scroll(250); await sleep(3000);

  await page.click('[data-a=signout]'); await page.waitForSelector('#loginform');
  await cap('Teacher: mobile number and a one-time code. In production it arrives by SMS.', 2000);
  await page.click('[data-a=lrole][data-v=teacher]'); await type('#f0', '9000000002'); await page.click('button[type=submit]'); await page.waitForSelector('#f1');
  const code = (await page.locator('body').innerText()).match(/Demo code: (\d{6})/)[1]; await sleep(800); await type('#f1', code); await page.click('button[type=submit]');
  await page.waitForSelector('.brief'); await sleep(1500);
  await cap('The class heatmap. Ravi’s row is fresh because his phone just synced. Warning icons mark students who have not.', 5500);
  await page.click('[data-a=heat][data-v=chapter]'); await sleep(2500); await page.click('[data-a=heat][data-v=topic]');
  await cap('Morning briefing: five things a teacher can act on at 8:30, with the weakest basic behind the test.', 1500);
  await page.evaluate(() => document.querySelector('.brief').scrollIntoView({ behavior: 'smooth', block: 'center' })); await sleep(6000);
  await cap('The teacher sets the test date once. Every plan and every parent note follows it.', 1500);
  const d = new Date(); d.setDate(d.getDate() + 3);
  const iso = d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
  await page.evaluate(() => document.querySelector('#tdate').scrollIntoView({ behavior: 'smooth', block: 'center' })); await sleep(1200);
  await page.fill('#tdate', iso); await page.dispatchEvent('#tdate', 'change');
  await page.waitForFunction(() => /in 3 days/.test(document.body.innerText)); await sleep(2500);
  await cap('Groups: Extend, Practise, Basics. The engine suggests, the teacher decides. Practice goes to those phones.', 1500);
  await page.evaluate(() => document.querySelector('.grp').scrollIntoView({ behavior: 'smooth', block: 'start' })); await sleep(2500);
  await page.click('[data-a=hw][data-v=basics]'); await sleep(3500);
  await page.evaluate(() => { const h = [...document.querySelectorAll('h2')].find(x => /Worksheets/.test(x.textContent)); h.scrollIntoView({ behavior: 'smooth', block: 'start' }); });
  await cap('Three-level worksheets instead of one sheet for the whole class.', 4000);

  await page.evaluate(() => window.scrollTo(0, 0)); await page.click('[data-a=signout]'); await page.waitForSelector('#loginform');
  await cap('Parent: own child only. A plain weekly note in English, Telugu or Hindi, with the new test date.', 1500);
  await page.click('[data-a=lrole][data-v=parent]'); await type('#f0', '9000000003'); await page.click('button[type=submit]'); await page.waitForSelector('#f1');
  const pc = (await page.locator('body').innerText()).match(/Demo code: (\d{6})/)[1]; await type('#f1', pc); await page.click('button[type=submit]');
  await page.waitForSelector('.bubble'); await sleep(4000);
  await page.click('[data-a=plang][data-v=te]'); await sleep(3500);
  await page.click('[data-a=plang][data-v=hi]'); await sleep(3000);
  await cap('No marks, no rank, no other child. The server only lets a parent read children linked to them.', 4000);

  await cap('', 0);
  if (ARCH) { await page.goto('file://' + ARCH); await sleep(600); await install(); await cap('Architecture: offline-first PWA, FastAPI + SQLAlchemy, Python engine, SQLite or PostgreSQL. The server re-marks every answer.', 7000); }
  await title('Built and tested', ['Python backend · 52 automated tests · real-browser end-to-end check', 'Phone and server engines proven identical · Docker, Postgres, CI', 'Thank you · Team WIN R'], 5000);
  await ctx.close(); await browser.close();
  console.log('recorded');
})().catch(e => { console.error('CRASH', e.message); process.exit(1); });
