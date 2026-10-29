/* Runs the phone engine (frontend/js/engine.js) in a sandbox and prints results as JSON for the Python parity test. */
const fs = require('fs'), vm = require('vm'), path = require('path');
const root = path.resolve(__dirname, '..');
const DATA = JSON.parse(fs.readFileSync(path.join(root, 'backend/data/curriculum.json'), 'utf8'));
const ctx = vm.createContext({ DATA, window: { addEventListener() {} }, navigator: { onLine: true },
  localStorage: { getItem() { return null; }, setItem() {}, removeItem() {} }, setInterval() {}, setTimeout() {}, console, Math, Date, JSON });
vm.runInContext(fs.readFileSync(path.join(root, 'frontend/js/api.js'), 'utf8').replace("'use strict';", ''), ctx, { filename: 'api.js' });
vm.runInContext(fs.readFileSync(path.join(root, 'frontend/js/engine.js'), 'utf8').replace("'use strict';", ''), ctx, { filename: 'engine.js' });
const run = s => vm.runInContext(s, ctx);
const seq = JSON.parse(process.argv[2] || '[]');
const out = {
  nudge: seq.map(([p, ok]) => run(`nudge(${p}, ${ok})`)),
  lvl: [0.1, 0.39, 0.4, 0.69, 0.7, 0.95].map(p => run(`wantLvl(${p})`)),
  closure: Object.fromEntries(Object.keys(DATA.T).map(t => [t, run(`allPre(${JSON.stringify(t)})`)])),
  readiness: run(`readiness({m8_alg:.4,m8_exp:.9}, chapters('TELANGANA',8,'Maths').slice(0,2))`),
};
console.log(JSON.stringify(out));
