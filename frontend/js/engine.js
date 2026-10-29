'use strict';
/* Sahayak engine, phone side. Topics, prerequisites, questions and chapter maps come from the server bundle.
   Practice runs here so it works with no network. Every answer goes into an outbox and is sent to the server, which
   marks it again against the curriculum and keeps the authoritative mastery (backend/app/engine mirrors these rules). */
const T=DATA.T,B=DATA.B,SUBJECTS=['Maths','Science'],BOARDS=['CBSE','ICSE','TELANGANA'];
const MIS_SHORT=s=>s;
const tn=(id,lang)=>lang==='te'?T[id].te:lang==='hi'?T[id].hi:T[id].name;

/* ---------- small helpers ---------- */
const WD=['Sun','Mon','Tue','Wed','Thu','Fri','Sat'],MON=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
const TODAY=(()=>{const d=new Date();return new Date(d.getFullYear(),d.getMonth(),d.getDate())})();
const pd=s=>{const [y,m,d]=s.split('-').map(Number);return new Date(y,m-1,d)};
const ds=d=>d.getFullYear()+'-'+String(d.getMonth()+1).padStart(2,'0')+'-'+String(d.getDate()).padStart(2,'0');
const addD=(d,n)=>{const x=new Date(d);x.setDate(x.getDate()+n);return x};
const dayDiff=(a,b)=>Math.round((Date.UTC(b.getFullYear(),b.getMonth(),b.getDate())-Date.UTC(a.getFullYear(),a.getMonth(),a.getDate()))/864e5);
const fd=d=>WD[d.getDay()]+' '+d.getDate()+' '+MON[d.getMonth()];
const fmtT=s=>{s=Math.max(0,Math.round(s));return Math.floor(s/60)+':'+String(s%60).padStart(2,'0')};
const rnd=(a,b)=>a+Math.floor(Math.random()*(b-a+1));
const shuffle=a=>{a=a.slice();for(let i=a.length-1;i>0;i--){const j=rnd(0,i);[a[i],a[j]]=[a[j],a[i]]}return a};
const pc=x=>Math.round(x*100)+'%';
const mean=a=>a.length?a.reduce((s,x)=>s+x,0)/a.length:0;
const uniq=a=>[...new Set(a)];
const rng=seed=>{let s=seed>>>0;return()=>{s=(Math.imul(s,1664525)+1013904223)>>>0;return s/4294967296}};

/* ---------- concept graph ---------- */
const _cl={};
function allPre(id){
  if(_cl[id])return _cl[id];
  const out=new Set();const walk=x=>T[x].pre.forEach(y=>{if(!out.has(y)){out.add(y);walk(y)}});walk(id);
  return _cl[id]=[...out];
}
const closureOf=ids=>uniq(ids.flatMap(allPre));
const classTopics=(cls,subj)=>Object.keys(T).filter(k=>T[k].cls===cls&&T[k].sub===subj);
const dependsOn=(t,g)=>allPre(t).includes(g);

/* ---------- curriculum layer: board > class > subject > chapters ---------- */
const chapters=(board,cls,subj)=>((B[board]||{}).classes||{})[cls]?.[subj]||[];
const chTopics=chs=>uniq(chs.flatMap(c=>c.topics));
const chMastery=(P,ch)=>mean(ch.topics.map(t=>P[t]??.5));
const readiness=(P,chs)=>mean(chTopics(chs).map(t=>P[t]??.5));

/* ---------- mastery: Bayesian knowledge tracing style, damped so one answer never swings it ---------- */
function bkt(p,ok){const s=.1,g=.22,l=.12;const pc_=p*(1-s)+(1-p)*g;const post=ok?p*(1-s)/pc_:p*s/(1-pc_);return Math.min(.98,post+(1-post)*l)}
const nudge=(p,ok)=>p+.55*(bkt(p,ok)-p);
const wantLvl=p=>p<.4?1:p<.7?2:3;

/* ---------- device storage ---------- */
const LS={get(k){try{return JSON.parse(localStorage.getItem(k))}catch(e){return null}},set(k,v){try{localStorage.setItem(k,JSON.stringify(v))}catch(e){}},del(k){try{localStorage.removeItem(k)}catch(e){}}};
const uid=()=>(window.crypto&&crypto.randomUUID?crypto.randomUUID():String(Date.now())+Math.random().toString(36).slice(2,10));

/* ---------- the student on this phone ---------- */
let PROFILE=null;
function blankProfile(u){
  return {id:u.id,name:u.name,board:u.board,cls:u.cls,lang:u.lang||'en',subj:u.subject||'Maths',P:{},asked:{},misc:{},mins:{},
    online:true,outbox:[],exv:{},lessonN:{},tests:{},groups:{},assignment:null,lastMock:null,
    prep:{mode:'test',term:ds(addD(TODAY,14))},syncedAt:null,syncErr:null};
}
const saveProfile=()=>{if(PROFILE)LS.set('sahayak.p.'+PROFILE.id,PROFILE)};
function applyServer(p,m){
  p.name=m.name;p.board=m.board;p.cls=m.cls;p.lang=p.lang||m.lang;p.tests=m.tests;p.groups=m.groups;p.assignment=m.assignment;
  p.misc={...m.misc};p.mins={...m.minutes};
  if(m.last_mock)p.lastMock={score:m.last_mock.score,total:m.last_mock.total,name:m.last_mock.name,subj:m.last_mock.subject};
  rebase(p,m.P);p.syncedAt=Date.now();
}
/* server mastery is the truth; answers still waiting in the outbox are laid on top so the phone never goes backwards */
function rebase(p,serverP){
  p.P={...serverP};
  p.outbox.forEach(e=>{if(e.type==='answer'&&e.lt)p.P[e.lt]=nudge(p.P[e.lt]??.5,!!e.lok)});
}
const pending=p=>p.outbox.length;
const me=()=>PROFILE;

/* ---------- session state (not saved) ---------- */
let S={auth:null,sv:'home',chi:null,D:null,M:null,mres:null,log:[],heat:'topic',
  tb:'TELANGANA',tc:8,ts:'Maths',pLang:'en',diag:null,td:null,terr:'',tload:false,hwNote:'',pk:null,pkids:[],pn:null,perr:''};
function log(s){S.log.unshift(s);S.log=S.log.slice(0,9)}
const subjChapters=p=>chapters(p.board,p.cls,p.subj);

/* ---------- the test the class is preparing for (set by the teacher, held on the server) ---------- */
function testOf(p,subj){
  const t=p.tests[subj],L=chapters(p.board,p.cls,subj);
  const list=(t?t.chapters:[]).map(n=>L.find(x=>x.name===n)).filter(Boolean);
  return {name:t?t.name:'Unit Test',date:t?t.date:ds(addD(TODAY,6)),list:list.length?list:L.slice(0,1)};
}
function exam(p){
  const L=subjChapters(p);
  if(p.prep.mode==='term')return {name:'Half-yearly exam',date:p.prep.term,list:L.slice(),by:'Date chosen by you',kind:'Half-yearly exam'};
  const t=testOf(p,p.subj);
  return {name:t.name,date:t.date,list:t.list,by:'Set by your teacher',kind:'Class test'};
}

/* ---------- adaptive practice ---------- */
const poolOf=(p,t)=>T[t].qs.filter(q=>!p.asked[q.id]);
function pick(p,t){
  let pl=poolOf(p,t);
  if(!pl.length)return null;
  const w=wantLvl(p.P[t]??.5);
  pl=pl.slice().sort((a,b)=>Math.abs(a.lvl-w)-Math.abs(b.lvl-w)||Math.random()-.5);
  return {...pl[0],qid:pl[0].id,t,o:shuffle(pl[0].o)};
}
function checkQs(p,ch,target){
  const ts=ch?ch.topics:[target];
  const all=ts.flatMap(t=>T[t].qs.map(q=>({...q,qid:q.id,t,id:'k'+q.id,o:shuffle(q.o)})));
  const w=wantLvl(mean(ts.map(t=>p.P[t]??.5)));
  const pool=shuffle(all).sort((a,b)=>Math.abs(a.lvl-w)-Math.abs(b.lvl-w));
  const out=[],seen=new Set();
  for(const q of pool){if(out.length>=3)break;if(ts.length>1&&seen.has(q.t)&&seen.size<Math.min(3,ts.length))continue;seen.add(q.t);out.push(q)}
  for(const q of pool){if(out.length>=3)break;if(!out.includes(q))out.push(q)}
  return out;
}
function startPractice(chi,forceT){
  const p=me(),ch=subjChapters(p)[chi];
  const t=forceT||ch.topics.slice().sort((a,b)=>(p.P[a]??.5)-(p.P[b]??.5))[0];
  p.asked={};
  S.D={chi,ch:ch.name,target:t,focus:t,learnFor:t,phase:'learn',answered:0,fb:null,q:null,recent:[],testQ:[],testI:0,testRes:[],
    startP:{...p.P},ctopics:ch.topics.slice(),catchup:!!forceT&&!ch.topics.includes(forceT)};
  S.sv='practice';
  log(`Practice started on ${T[t].name} (${ch.name}).`);
  if(!forceT||p.lessonN[t])S.D.phase='learn';
}
function startCatchup(t){
  const p=me(),chi=Math.max(0,subjChapters(p).findIndex(c=>c.topics.some(x=>dependsOn(x,t))));
  startPractice(chi,t);
}
function startCheckFor(chi){
  const p=me(),ch=subjChapters(p)[chi];p.asked={};
  S.D={chi,ch:ch.name,target:ch.topics[0],focus:ch.topics[0],learnFor:ch.topics[0],phase:'test',answered:0,fb:null,q:null,recent:[],testQ:[],testI:0,testRes:[],
    startP:{...p.P},ctopics:ch.topics.slice()};
  S.sv='practice';beginCheck();
}
function beginCheck(){
  const p=me(),D=S.D,ch=subjChapters(p)[D.chi];
  D.phase='test';D.testQ=checkQs(p,ch,D.target);D.testI=0;D.testRes=[];D.q=D.testQ[0];D.fb=null;
  log(`Starting a ${D.testQ.length}-question check on ${ch.name}. No hints this time.`);
}
function loadNext(){
  const p=me(),D=S.D,T0=D.target;
  if(D.answered>=8||(D.focus===T0&&(p.P[T0]??.5)>=.85&&D.answered>=4))return beginCheck();
  const q=pick(p,D.focus)||pick(p,T0);
  if(!q)return beginCheck();
  D.q=q;D.fb=null;D.phase='solve';
}
function leaveLesson(){const p=me(),D=S.D;p.lessonN[D.learnFor]=(p.lessonN[D.learnFor]||0)+1;saveProfile();loadNext()}
function weakestPre(p,t){return allPre(t).slice().sort((a,b)=>(p.P[a]??.5)-(p.P[b]??.5))[0]}
function queue(p,ev){p.outbox.push(ev);saveProfile()}
function answer(i){
  const p=me(),D=S.D,q=D.q;if(!q||D.fb)return;
  const T0=D.target,o=q.o[i],ok=!!o.ok,before=p.P[q.t]??.5;
  p.P[q.t]=nudge(before,ok);p.asked[q.id]=1;
  p.mins[ds(TODAY)]=(p.mins[ds(TODAY)]||0)+1.2;D.recent.push(ok);
  if(!ok)p.misc[o.m]=(p.misc[o.m]||0)+1;
  /* what goes to the server is what was picked. lt/lok/lm are local-only and are stripped before sending */
  queue(p,{cid:uid(),type:'answer',kind:D.phase==='test'?'check':'practice',qid:q.qid,pick:o.t,ts:new Date().toISOString(),lt:q.t,lok:ok,lm:ok?null:o.m});
  log(`${T[q.t].name}: ${ok?'correct':'wrong'}. Mastery ${pc(before)} to ${pc(p.P[q.t])}.`);
  if(D.phase==='test'){
    D.testRes.push(ok);D.testI++;
    if(D.testI>=D.testQ.length){D.phase='done';D.q=null;log('Check finished. Results saved on the phone.');syncSoon(0)}else D.q=D.testQ[D.testI];
    saveProfile();return;
  }
  D.answered++;
  D.fb={ok,why:q.why,m:o.m||null,pre:null,back:false,picked:i};
  if(!ok){
    let tr=null;
    if(o.g&&(p.P[o.g]??.5)<.75)tr=o.g;
    else if(q.t===T0){const w=allPre(T0).filter(c=>(p.P[c]??.5)<.6&&poolOf(p,c).length).sort((a,b)=>(p.P[a]??.5)-(p.P[b]??.5));tr=w[0]||null}
    if(tr&&tr!==q.t){
      D.fb.pre=tr;D.focus=tr;D.learnFor=tr;
      log(`Mistake pattern "${o.m}" points to ${T[tr].name} (${pc(p.P[tr]??.5)}). Switching to that basic.`);
    }
  }else if(D.focus!==T0&&(p.P[D.focus]??.5)>=.7){
    D.focus=T0;D.fb.back=true;log(`That basic looks steady now. Returning to ${T[T0].name}.`);
  }
  saveProfile();syncSoon();
}
function next(){
  const p=me(),D=S.D;
  if(D.fb&&D.fb.pre&&(p.P[D.fb.pre]??.5)<.6){D.phase='learn';D.learnFor=D.fb.pre;D.q=null;D.fb=null;return}
  loadNext();
}

/* ---------- sync: outbox up, authoritative state down. Retrying is safe, the server ignores events it has seen ---------- */
let _syncing=false,_timer=null;
const canNet=p=>p.online&&navigator.onLine!==false;
const WIRE=['cid','type','ts','kind','qid','pick','answers','rows','name','subject','minutes'];
function syncSoon(ms=1200){clearTimeout(_timer);_timer=setTimeout(()=>sync(me()),ms)}
async function sync(p){
  if(!p||_syncing||!canNet(p)||!p.outbox.length||!API.token)return;
  _syncing=true;const batch=p.outbox.slice();
  try{
    const r=await API.post('/sync',{events:batch.map(e=>Object.fromEntries(WIRE.filter(k=>e[k]!==undefined&&e[k]!==null).map(k=>[k,e[k]])))});
    const done=new Set(batch.map(e=>e.cid));
    p.outbox=p.outbox.filter(e=>!done.has(e.cid));
    p.misc={...r.misc};p.mins={...r.minutes};
    p.outbox.forEach(e=>{if(e.lm)p.misc[e.lm]=(p.misc[e.lm]||0)+1});
    rebase(p,r.P);p.syncedAt=Date.now();p.syncErr=null;
    log(`Synced ${r.accepted} saved ${r.accepted===1?'item':'items'} to the server${r.duplicates?` (${r.duplicates} already there)`:''}.`);
    if(r.rejected.length)log(`${r.rejected.length} items were not accepted by the server.`);
  }catch(e){
    p.syncErr=e.status===401?'auth':'offline';
    if(e.status===401)authLost();
  }finally{_syncing=false;saveProfile();if(typeof render==='function'&&S.auth==='student')render()}
}
function toggleNet(){
  const p=me();p.online=!p.online;
  if(p.online){const n=pending(p);log(n?`Back online. Sending ${n} saved items.`:'Back online. Nothing waiting to send.');sync(p)}
  else log('Offline. Answers are saved on this phone and the engine keeps working.');
  saveProfile();
}
window.addEventListener('online',()=>{if(PROFILE)sync(PROFILE)});
setInterval(()=>{if(PROFILE)sync(PROFILE)},30000);

/* ---------- placement check: a few questions on the foundations behind the chapters ---------- */
function startPlacement(){
  const p=me(),L=subjChapters(p),ct=chTopics(L);
  const cnt={};ct.forEach(t=>allPre(t).forEach(g=>{cnt[g]=(cnt[g]||0)+1}));
  let foundations=Object.keys(cnt).sort((a,b)=>cnt[b]-cnt[a]||T[a].cls-T[b].cls).slice(0,5);
  if(foundations.length<5)foundations=uniq([...foundations,...ct]).slice(0,5);
  const qs=foundations.map(t=>{const w=T[t].qs.filter(q=>q.lvl===2);const q=w[Math.floor(Math.random()*w.length)]||T[t].qs[0];return {...q,qid:q.id,t,id:'d'+q.id,o:shuffle(q.o)}});
  S.diag={qs,i:0,res:[],ans:[],fb:null};S.sv='diag';
  log(`Placement check: ${qs.length} questions on foundation topics, to set a starting picture.`);
}
function diagAnswer(i){
  const p=me(),Dg=S.diag,q=Dg.qs[Dg.i];if(Dg.fb)return;
  const o=q.o[i],ok=!!o.ok;
  p.P[q.t]=nudge(.5,ok);Dg.res.push(ok);Dg.ans.push({qid:q.qid,pick:o.t});Dg.fb={ok,picked:i,why:q.why,m:o.m||null};
  if(!ok)p.misc[o.m]=(p.misc[o.m]||0)+1;
}
function diagNext(){
  const p=me(),Dg=S.diag;
  Dg.i++;Dg.fb=null;
  if(Dg.i>=Dg.qs.length){
    /* spread what we learned to related topics that have no data yet */
    Dg.qs.forEach(q=>{
      const v=p.P[q.t];
      Object.keys(T).forEach(t=>{if(p.P[t]===undefined&&T[t].sub===T[q.t].sub&&(dependsOn(t,q.t)||dependsOn(q.t,t)))p.P[t]=.5+(v-.5)*.5});
    });
    queue(p,{cid:uid(),type:'placement',ts:new Date().toISOString(),answers:Dg.ans});
    log(`Placement done: ${Dg.res.filter(Boolean).length} of ${Dg.qs.length} correct. Starting picture saved.`);
    saveProfile();syncSoon(0);S.sv='home';S.diag=null;
  }
}

/* ---------- revision plan and mock tests ---------- */
function planFor(p,ex){
  const days=dayDiff(TODAY,pd(ex.date));
  if(days<=0)return {days,items:[]};
  const P=p.P,inT=new Set(chTopics(ex.list)),pre=[];
  ex.list.forEach(ch=>ch.topics.forEach(t=>allPre(t).forEach(g=>{if(!inT.has(g)&&(P[g]??.5)<.6&&!pre.some(x=>x.t===g))pre.push({t:g,f:ch.name})})));
  pre.sort((a,b)=>(P[a.t]??.5)-(P[b.t]??.5));
  const need={};ex.list.forEach(ch=>need[ch.name]=1-chMastery(P,ch)+.15);
  const items=[];
  for(let i=0;i<days&&i<14;i++){
    const when=addD(TODAY,i);
    if(i===days-1){items.push({when,kind:'mock',title:'Mock test, then fix the slips',why:'Timed, marked by steps where the subject allows',mins:25});continue}
    if(pre.length){const x=pre.shift();items.push({when,kind:'catchup',t:x.t,title:`Catch-up: ${T[x.t].name}`,why:`${pc(P[x.t]??.5)} now, and ${x.f} builds on it`,mins:15});continue}
    const ch=ex.list.slice().sort((a,b)=>need[b.name]-need[a.name])[0];need[ch.name]-=.35;
    items.push({when,kind:'practice',ch:ch.name,title:`Practise ${ch.name}`,why:`${pc(chMastery(P,ch))} now`,mins:20});
  }
  return {days,items};
}
function mockBuild(p,list){
  const P=p.P,ts=chTopics(list).sort((a,b)=>(P[a]??.5)-(P[b]??.5)),items=[],used=new Set();
  const withSteps=p.subj==='Maths'?ts.filter(t=>T[t].steps):[];
  const nMcq=withSteps.length?4:5;
  for(let i=0;i<nMcq;i++){
    const t=ts[i%ts.length];
    const pl=shuffle(T[t].qs.filter(q=>!used.has(q.id)));
    const q=pl.sort((a,b)=>Math.abs(a.lvl-wantLvl(P[t]??.5))-Math.abs(b.lvl-wantLvl(P[t]??.5)))[0]||T[t].qs[0];
    used.add(q.id);items.push({kind:'mcq',marks:1,q:{...q,t,o:shuffle(q.o)}});
  }
  if(withSteps.length){
    const t=withSteps[0],st=T[t].steps;
    items.push({kind:'steps',marks:3,q:{t,q:st.q,steps:st.parts.map(x=>({...x,o:shuffle(x.o)}))}});
  }
  return items;
}
function startMock(){
  const p=me(),ex=exam(p),items=mockBuild(p,ex.list),total=items.reduce((a,x)=>a+x.marks,0);
  S.M={items,i:0,si:0,cur:[],rows:[],t0:Date.now(),qt:Date.now(),limit:Math.max(6,total+3)*60,name:ex.name};
  S.sv='mock';log(`Mock test started for ${ex.name}: ${total} marks.`);
}
function mockAnswer(j){
  const K=S.M,it=K.items[K.i],now=Date.now();
  if(it.kind==='mcq'){
    const o=it.q.o[j];
    K.rows.push({kind:'mcq',marks:1,got:o.ok?1:0,t:it.q.t,qid:it.q.id,q:it.q.q,picked:o.t,right:it.q.o.find(x=>x.ok).t,m:o.ok?null:o.m,secs:(now-K.qt)/1000});
    K.i++;K.qt=now;
  }else{
    const st=it.q.steps[K.si],o=st.o[j];
    K.cur.push({label:st.label,ok:!!o.ok,picked:o.t,right:st.o.find(x=>x.ok).t,m:o.ok?null:o.m});
    K.si++;
    if(K.si>=it.q.steps.length){
      K.rows.push({kind:'steps',marks:it.marks,got:K.cur.filter(x=>x.ok).length,t:it.q.t,q:it.q.q,steps:K.cur,secs:(now-K.qt)/1000});
      K.cur=[];K.si=0;K.i++;K.qt=now;
    }
  }
  if(K.i>=K.items.length)finishMock();
}
function finishMock(){
  const p=me(),K=S.M;
  const score=K.rows.reduce((a,r)=>a+r.got,0),total=K.rows.reduce((a,r)=>a+r.marks,0);
  K.rows.forEach(r=>{
    p.P[r.t]=nudge(p.P[r.t]??.5,r.got===r.marks);
    if(r.kind==='mcq'&&r.m)p.misc[r.m]=(p.misc[r.m]||0)+1;
    if(r.kind==='steps')r.steps.forEach(s=>{if(s.m)p.misc[s.m]=(p.misc[s.m]||0)+1});
  });
  const mins=Math.round((Date.now()-K.t0)/60000)||1;p.mins[ds(TODAY)]=(p.mins[ds(TODAY)]||0)+mins;
  p.lastMock={score,total,when:fd(TODAY),name:K.name,subj:p.subj};
  S.mres={rows:K.rows,score,total,secs:(Date.now()-K.t0)/1000,limit:K.limit};
  S.sv='mockdone';
  queue(p,{cid:uid(),type:'mock',ts:new Date().toISOString(),name:K.name,subject:p.subj,minutes:Math.min(180,mins),
    rows:K.rows.map(r=>r.kind==='mcq'?{kind:'mcq',qid:r.qid,pick:r.picked}:{kind:'steps',topic:r.t,picks:r.steps.map(s=>s.picked)})});
  log(`Mock finished: ${score} of ${total} marks. Mastery updated from the paper.`);
  if(!canNet(p))log('Offline: the result will reach the teacher when you are back online.');
  saveProfile();syncSoon(0);
}
