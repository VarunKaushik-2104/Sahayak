/* End-to-end check in a real browser: teacher signs up -> student joins with the school code -> offline -> sync -> teacher sees the student -> parent links with the family code.
   Usage: node scripts/e2e.js [baseUrl] [screenshotDir]   (needs playwright; start the server on an EMPTY database, no demo data: everything below is created through the screens) */
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

  const signup = async (role, fields) => {
    await page.click(`[data-a=lrole][data-v=${role}]`); await page.click('[data-a=lmode][data-v=up]');
    for (const [id, v] of Object.entries(fields)) await page.fill('#' + id, v);
    await page.click('button[type=submit]');
  };

  // ---- the public website (server-rendered, crawlable)
  await page.goto(BASE + '/');
  ok(/Find the gap behind the wrong answer/.test(await text()), 'home page renders');
  ok((await page.locator('script[type="application/ld+json"]').count()) >= 3, 'home page carries JSON-LD');
  await shot('00-home');
  await page.goto(BASE + '/topics/m10_quad'); ok(/Mistakes students commonly make/.test(await text()), 'topic page renders from real data');
  await shot('00-topic');
  await page.goto(BASE + '/app/'); await page.waitForSelector('#loginform');

  // ---- a new school: nothing is invented for it
  ok(!/Ravi|Ms\. Lakshmi|Demo|sample classmates/i.test(await text()), 'sign-in screen shows no demo accounts or demo text');
  await signup('teacher', { sn: 'Mr. Rao', se: 'rao@example.com', sp: 'strong-pass-1', ss: 'Greenfield High School' });
  await page.waitForSelector('.code'); const schoolCode = (await page.locator('.code').first().innerText()).trim();
  ok(/^[A-Z2-9]{6}$/.test(schoolCode), 'teacher account created; school code ' + schoolCode);
  ok(/No students in this class yet/.test(await text()), 'a new school starts empty');
  await shot('01-teacher-new-school');
  await page.click('[data-a=signout]'); await page.waitForSelector('#loginform');

  // ---- a student joins with that code
  await page.click('[data-a=lrole][data-v=student]');
  await page.fill('#nn', 'Asha'); await page.fill('#sc', schoolCode.toLowerCase()); await page.fill('#np', '4321');
  await page.click('button[type=submit]'); await page.waitForSelector('.phone');
  ok(true, 'student profile created with the school code'); await shot('02-home');
  ok(/Joined\s+Greenfield High School/.test(await text()), 'student sees the school they joined');
  const familyCode = (await page.locator('.code[aria-label="Family code"]').innerText()).trim();
  ok(/^[A-Z2-9]{6}$/.test(familyCode), 'student has a family code ' + familyCode);

  // placement check
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
  ok(me.name === 'Asha' && me.school && me.school.name === 'Greenfield High School', 'server state readable with the session token, school joined');

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

  // ---- teacher signs back in with email and password and sees the real student
  await page.click('[data-a=signout]'); await page.waitForSelector('#loginform');
  await page.click('[data-a=lrole][data-v=teacher]');
  await page.fill('#se', 'rao@example.com'); await page.fill('#sp', 'wrong-password'); await page.click('button[type=submit]');
  await page.waitForSelector('.err'); ok(/does not match/.test(await text()), 'wrong password is refused');
  await page.fill('#sp', 'strong-pass-1'); await page.click('button[type=submit]');
  await page.waitForSelector('.brief'); await shot('09-teacher');
  const tt = await text();
  ok(/Asha/.test(tt) && /Morning briefing/.test(tt), 'teacher sees the student who joined, and the briefing');
  ok(/1 student has joined/.test(tt), 'school card counts the joined student');
  const row = await page.locator('tr', { hasText: 'Asha' }).first().innerText();
  ok(!/⚠/.test(row), 'student is not stale after syncing');
  await page.click('[data-a=heat][data-v=chapter]'); await shot('10-teacher-chapters');
  const d = new Date(); d.setDate(d.getDate() + 3);
  const iso = d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
  await page.fill('#tdate', iso); await page.dispatchEvent('#tdate', 'change');
  await page.waitForFunction(() => /in 3 days/.test(document.body.innerText), null, { timeout: 8000 });
  ok(true, 'teacher moved the test date; briefing now says 3 days');
  await page.click('[data-a=hw][data-v=basics], [data-a=hw][data-v=practise], [data-a=hw][data-v=extend]:not([disabled])').catch(() => {});
  const hwBtn = page.locator('[data-a=hw]:not([disabled])').first(); await hwBtn.click();
  await page.waitForFunction(() => /Sent:/.test(document.body.innerText)); ok(true, 'teacher sent practice to a group');
  await shot('11-teacher-groups');

  // ---- a parent links the child with the family code
  await page.click('[data-a=signout]'); await page.waitForSelector('#loginform');
  await page.click('[data-a=lrole][data-v=parent]'); await page.click('[data-a=lmode][data-v=up]');
  await page.fill('#sn', 'Mrs. Rao'); await page.fill('#se', 'mrs.rao@example.com'); await page.fill('#sp', 'another-pass-1'); await page.fill('#sf', 'WRONG1');
  await page.click('button[type=submit]'); await page.waitForSelector('.err'); ok(/family code was not found/.test(await text()), 'a wrong family code is refused');
  await page.fill('#sp', 'another-pass-1'); await page.fill('#sf', familyCode.toLowerCase()); await page.click('button[type=submit]');
  await page.waitForSelector('.bubble');
  ok(/in 3 days/.test(await text()), 'parent note follows the teacher\'s new test date');
  const bub = await page.locator('.bubble').innerText(); ok(!/rank|score/i.test(bub), 'parent note gives no rank or score');
  await page.click('[data-a=plang][data-v=te]'); await page.waitForFunction(() => /నమస్కారం/.test(document.body.innerText));
  await shot('12-parent-telugu'); ok(true, 'Telugu note renders');
  await page.click('[data-a=plang][data-v=hi]'); await page.waitForFunction(() => /नमस्ते/.test(document.body.innerText));
  ok(true, 'Hindi note renders');

  // ---- the student sees the teacher's changes, and one parent follows
  await page.click('[data-a=signout]'); await page.waitForSelector('#loginform');
  await page.click('[data-a=lrole][data-v=student]'); await page.fill('#f1', '4321'); await page.click('button[type=submit]');
  await page.waitForSelector('.phone');
  await page.waitForFunction(() => /Your teacher sent/.test(document.body.innerText), null, { timeout: 8000 });
  ok(/in 3 days/.test(await text()), 'student sees the new test date and the practice the teacher sent');
  await page.waitForFunction(() => /1 parent follows/.test(document.body.innerText), null, { timeout: 8000 });
  ok(true, 'student sees that one parent follows'); await shot('13-student-after');

  // ---- the student deletes the account
  page.once('dialog', d => d.accept());
  await page.click('[data-a=delacct]'); await page.waitForSelector('#loginform');
  const rows = await page.evaluate(async () => (await (await fetch('/api/auth/demo-profiles')).json()).length);
  ok(rows === 0, 'account deleted; no profile left on this phone');
  ok(!/Asha/.test(await text()), 'deleted student no longer offered on the sign-in screen');

  ok(errors.length === 0, 'no browser errors' + (errors.length ? ': ' + errors.slice(0, 3).join(' | ') : ''));
  await browser.close();
})().catch(e => { console.error('CRASH', e.message); process.exit(1); });
