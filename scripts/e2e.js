/* End-to-end check in a real browser: student -> offline -> sync -> teacher -> parent.
   Usage: node scripts/e2e.js [baseUrl] [screenshotDir]   (needs playwright; the server must be running with SEED_DEMO=1) */
const { chromium } = require(process.env.PLAYWRIGHT_PATH || 'playwright');
const fs = require('fs');
const BASE = process.argv[2] || 'http://localhost:8765';
const SHOTS = process.argv[3] || null;
const ok = (c, m) => { if (!c) { console.error('FAIL:', m); process.exitCode = 1; } else console.log('ok  :', m); };
const errors = [];

(async () => {
  if (SHOTS) fs.mkdirSync(SHOTS, { recursive: true });
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const page = await ctx.newPage();
  page.on('pageerror', e => errors.push(String(e)));
  page.on('console', m => { if (m.type() === 'error' && !/favicon|Failed to load resource/.test(m.text())) errors.push(m.text()); });
  const shot = async n => { if (SHOTS) await page.screenshot({ path: `${SHOTS}/${n}.png` }); };
  const text = () => page.locator('body').innerText();
  const api = (path, tok) => page.evaluate(async ([p, t]) => (await fetch('/api' + p, { headers: { Authorization: 'Bearer ' + t } })).json(), [path, tok]);
  const token = () => page.evaluate(() => JSON.parse(localStorage.getItem('sahayak.session')).token);

  await page.goto(BASE); await page.waitForSelector('#loginform');
  await shot('01-login');
  ok(/Ravi K\./.test(await text()), 'login shows the demo profile');

  // wrong PIN
  await page.fill('#f1', '9999'); await page.click('button[type=submit]');
  await page.waitForSelector('.err'); ok(/does not match/.test(await text()), 'wrong PIN is refused');
  await page.fill('#f1', '1234'); await page.click('button[type=submit]');
  await page.waitForSelector('.phone'); ok(true, 'student signs in with PIN');
  await shot('02-home');

  // placement check: answer the first option each time
  await page.click('[data-a=diag]');
  for (let i = 0; i < 5; i++) { await page.click('[data-a=dans] >> nth=0'); await page.click('[data-a=dnext]'); }
  await page.waitForFunction(() => !document.querySelector('[data-a=dans]'));
  await page.waitForFunction(() => /Outbox:\s*0 items/.test(document.body.innerText), null, { timeout: 8000 });
  ok(true, 'placement check synced, outbox empty');

  // practise a chapter online
  await page.click('[data-a=chapter] >> nth=0'); await shot('03-chapter');
  await page.click('[data-a=startp]');
  if (await page.locator('[data-a=learned]').count()) await page.click('[data-a=learned]');
  for (let i = 0; i < 3; i++) {
    await page.click('[data-a=ans] >> nth=0');
    await shot('04-practice-' + i);
    await page.click('[data-a=next]');
    if (await page.locator('[data-a=learned]').count()) await page.click('[data-a=learned]');
  }
  await page.waitForFunction(() => /Outbox:\s*0 items/.test(document.body.innerText), null, { timeout: 8000 });
  const tok = await token();
  const me = await api('/student/me', tok);
  const serverCount = await page.evaluate(async t => (await (await fetch('/api/student/me', { headers: { Authorization: 'Bearer ' + t } })).json()).minutes, tok);
  ok(Object.values(serverCount).reduce((a, b) => a + b, 0) > 0, 'server recorded study minutes from the synced answers');
  ok(me.name === 'Ravi K.', 'server state readable with the session token');

  // offline: answers queue, then send when back online
  const goHome = async () => { for (let i = 0; i < 4 && !(await page.locator('[data-a=chapter]').count()); i++) await page.locator('.back').first().click(); };
  await goHome();
  await page.evaluate(() => { document.querySelector('[data-a=net]').click(); });
  ok(/Offline/.test(await text()), 'phone switched to offline');
  await page.click('[data-a=chapter] >> nth=0'); await page.click('[data-a=startp]');
  if (await page.locator('[data-a=learned]').count()) await page.click('[data-a=learned]');
  for (let i = 0; i < 2; i++) { await page.click('[data-a=ans] >> nth=0'); await page.click('[data-a=next]'); if (await page.locator('[data-a=learned]').count()) await page.click('[data-a=learned]'); }
  const t1 = await text(); ok(/Outbox:\s*[1-9]/.test(t1), 'offline answers wait in the outbox');
  await shot('05-offline-outbox');
  await page.evaluate(() => { document.querySelector('[data-a=net]').click(); });
  await page.waitForFunction(() => /Outbox:\s*0 items/.test(document.body.innerText), null, { timeout: 8000 });
  ok(true, 'outbox drained after going back online'); await shot('06-synced');

  // mock test, marked on the server
  await goHome();
  await page.click('[data-a=nav][data-v=prep]'); await shot('07-plan');
  await page.click('[data-a=mock]');
  for (let i = 0; i < 12 && (await page.locator('[data-a=mans]').count()); i++) await page.click('[data-a=mans] >> nth=0');
  await page.waitForSelector('.rlist'); await shot('08-mock-result');
  await page.waitForFunction(() => /Outbox:\s*0 items/.test(document.body.innerText) || true);
  await page.waitForTimeout(2500);
  const lm = await api('/student/me', await token());
  ok(lm.last_mock && lm.last_mock.total >= 5, 'mock result stored on the server (' + JSON.stringify(lm.last_mock) + ')');

  // teacher
  await page.click('[data-a=signout]'); await page.waitForSelector('#loginform');
  await page.click('[data-a=lrole][data-v=teacher]');
  await page.fill('#f0', '9000000002'); await page.click('button[type=submit]');
  await page.waitForSelector('#f1'); ok(/Demo code: \d{6}/.test(await text()), 'OTP shown in demo mode');
  const code = (await text()).match(/Demo code: (\d{6})/)[1];
  await page.fill('#f1', code); await page.click('button[type=submit]');
  await page.waitForSelector('.brief'); await shot('09-teacher');
  const tt = await text();
  ok(/Ravi K\./.test(tt) && /Morning briefing/.test(tt), 'teacher sees the class and briefing');
  const raviRow = await page.locator('tr', { hasText: 'Ravi K.' }).first().innerText();
  ok(!/⚠/.test(raviRow), 'Ravi is no longer marked stale after syncing');
  await page.click('[data-a=heat][data-v=chapter]'); await shot('10-teacher-chapters');
  // move the test date
  const d = new Date(); d.setDate(d.getDate() + 3);
  const iso = d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
  await page.fill('#tdate', iso); await page.dispatchEvent('#tdate', 'change');
  await page.waitForFunction(() => /in 3 days/.test(document.body.innerText), null, { timeout: 8000 });
  ok(true, 'teacher moved the test date; briefing now says 3 days');
  await page.click('[data-a=hw][data-v=basics]'); await page.waitForFunction(() => /Sent:/.test(document.body.innerText));
  ok(true, 'teacher sent practice to a group');
  await shot('11-teacher-groups');

  // parent
  await page.click('[data-a=signout]'); await page.click('[data-a=lrole][data-v=parent]');
  await page.fill('#f0', '9000000003'); await page.click('button[type=submit]');
  await page.waitForSelector('#f1'); const pc = (await text()).match(/Demo code: (\d{6})/)[1];
  await page.fill('#f1', pc); await page.click('button[type=submit]');
  await page.waitForSelector('.bubble');
  let pt = await text(); ok(/in 3 days/.test(pt), 'parent note follows the teacher\'s new test date');
  const bub = await page.locator('.bubble').innerText(); ok(!/Ananya|Imran|rank|score/i.test(bub), 'parent note names no other child and gives no rank');
  await page.click('[data-a=plang][data-v=te]'); await page.waitForFunction(() => /నమస్కారం/.test(document.body.innerText));
  await shot('12-parent-telugu'); ok(true, 'Telugu note renders');
  await page.click('[data-a=plang][data-v=hi]'); await page.waitForFunction(() => /नमस्ते/.test(document.body.innerText));
  ok(true, 'Hindi note renders');

  // student sees teacher's changes
  await page.click('[data-a=signout]'); await page.waitForSelector('#loginform');
  await page.click('[data-a=lrole][data-v=student]'); await page.fill('#f1', '1234'); await page.click('button[type=submit]');
  await page.waitForSelector('.phone');
  await page.waitForFunction(() => /Your teacher sent/.test(document.body.innerText), null, { timeout: 8000 });
  ok(/in 3 days/.test(await text()), 'student sees the new test date and the practice the teacher sent');
  await shot('13-student-after');

  ok(errors.length === 0, 'no browser errors' + (errors.length ? ': ' + errors.slice(0, 3).join(' | ') : ''));
  await browser.close();
})().catch(e => { console.error('CRASH', e.message); process.exit(1); });
