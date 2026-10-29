'use strict';
const $=id=>document.getElementById(id);
const esc=s=>String(s==null?'':s).replace(/&/g,'&amp;').replace(/</g,'&lt;');
const mc=p=>p<.45?'m-bad':p<.7?'m-warn':'m-good';
const fc=p=>p<.45?'f-bad':p<.7?'f-warn':'f-good';
const bar=p=>`<span class="mbar ${fc(p)}"><i style="width:${Math.round(p*100)}%"></i></span>`;
const UI={
  en:{start:'Start practice',next:'Next',learn:'Learn',solve:'Solve',test:'Test',chapters:'Chapters',prep:'Prepare for this test',ready:'ready',online:'Online',offline:'Offline',subject:'Subject',placement:'Quick placement check',explain:'Explain differently',practise:'Practise this chapter',check:'Chapter check',today:'Today'},
  hi:{start:'अभ्यास शुरू करें',next:'आगे',learn:'सीखें',solve:'हल करें',test:'जाँच',chapters:'अध्याय',prep:'इस परीक्षा की तैयारी करें',ready:'तैयार',online:'ऑनलाइन',offline:'ऑफ़लाइन',subject:'विषय',placement:'शुरुआती जाँच',explain:'दूसरे तरीके से समझाएँ',practise:'इस अध्याय का अभ्यास',check:'अध्याय जाँच',today:'आज'},
  te:{start:'సాధన ప్రారంభించండి',next:'తరువాత',learn:'నేర్చుకో',solve:'సాధన',test:'పరీక్ష',chapters:'అధ్యాయాలు',prep:'ఈ పరీక్షకు సిద్ధం అవ్వండి',ready:'సిద్ధం',online:'ఆన్‌లైన్',offline:'ఆఫ్‌లైన్',subject:'సబ్జెక్టు',placement:'ప్రాథమిక పరీక్ష',explain:'వేరే విధంగా వివరించు',practise:'ఈ అధ్యాయం సాధన',check:'అధ్యాయ పరీక్ష',today:'ఈరోజు'}
};
const BNAME=b=>DATA.B[b].label;
const SENDMSG=p=>pending(p)?(canNet(p)?'Saved. Sending to your teacher now.':'Saved on this phone. It will be sent when you are back online.'):'Saved and sent to your teacher.';
const TRY={
  student:'<b>Try it:</b> run the placement check, open a chapter and practise, then tap <b>Prepare for this test</b> and take a mock. Switch the phone to Offline and answer more: the outbox fills, and everything sends when you go back online.',
  teacher:'<b>You are the teacher.</b> Pick a board, class and subject. You see the class, the morning briefing and worksheets, set the test date and chapters, and move students between groups. Students and parents only ever see their own data.',
  parent:'<b>You are the parent.</b> You see a plain note about your own child, with the test date, in your language. No marks, no rank, no other children.'
};
function fmtSync(iso){
  if(!iso)return 'never';
  const d=new Date(iso),days=Math.floor((Date.now()-d)/864e5);
  return days>=1?days+(days===1?' day ago':' days ago'):'Today '+d.toLocaleTimeString('en-IN',{hour:'numeric',minute:'2-digit'});
}

/* ---------- Sign in ---------- */
const LG={role:'student',pid:null,err:'',creating:false,busy:false,step:0,mobile:'',devCode:'',demo:[],
  draft:{name:'',pin:'',board:'TELANGANA',cls:8,lang:'en'}};
const deviceProfiles=()=>{
  const l=DEV.list().map(x=>({id:x.id,name:x.name,cls:x.cls,board:x.board}));
  LG.demo.forEach(d=>{if(!l.some(x=>x.id===d.id))l.push(d)});
  return l;
};
async function loadDemoProfiles(){try{LG.demo=await API.get('/auth/demo-profiles')}catch(e){LG.demo=[]}render()}
function vLogin(){
  const r=LG.role,P=deviceProfiles();
  if(!LG.pid||!P.some(p=>p.id===LG.pid))LG.pid=P[0]&&P[0].id;
  const roles=[['student','Student','Own profile and a 4-digit PIN, even on a shared phone'],['teacher','Teacher','Mobile number and a one-time code'],['parent','Parent','Mobile number and a one-time code']];
  const cards=roles.map(([k,t,d])=>`<button class="role" data-a="lrole" data-v="${k}" aria-pressed="${r===k}"><h3>${t}</h3><span class="note">${d}</span></button>`).join('');
  const chip=(a,v,l,on)=>`<button type="button" class="chip" data-a="${a}" data-v="${v}" aria-pressed="${on}">${l}</button>`;
  let form='',btn='';
  if(r==='student'&&LG.creating){
    const d=LG.draft;
    form=`<div><label class="k" for="nn">Name</label><input id="nn" class="in" value="${esc(d.name)}" autocomplete="off" placeholder="First name"></div>
      <div><label class="k">Board</label><div class="chips">${BOARDS.map(b=>chip('dboard',b,esc(BNAME(b)),d.board===b)).join('')}</div></div>
      <div><label class="k">Class</label><div class="chips">${[6,7,8,9,10].map(n=>chip('dcls',n,n,d.cls===n)).join('')}</div></div>
      <div><label class="k">Language</label><div class="chips">${[['en','English'],['te','తెలుగు'],['hi','हिन्दी']].map(([v,l])=>chip('dlang',v,l,d.lang===v)).join('')}</div></div>
      <div><label class="k" for="np">Choose a 4-digit PIN</label><input id="np" class="in" type="password" inputmode="numeric" maxlength="4" autocomplete="off" placeholder="4 digits"></div>
      <p class="note">Only what is needed: a first name, board, class, language. Needs a connection once.</p>`;
    btn='Create profile';
  }else if(r==='student'){
    form=`<div><label class="k">Who is using this phone?</label><div class="profiles">${P.map(p=>`<button type="button" class="chip" data-a="lprofile" data-v="${p.id}" aria-pressed="${LG.pid===p.id}"><span class="av">${esc(p.name[0])}</span>${esc(p.name)} · Class ${p.cls}</button>`).join('')}
      <button type="button" class="chip" data-a="lnew">+ New profile</button></div></div>
      <div><label class="k" for="f1">PIN</label><input id="f1" class="in" type="password" inputmode="numeric" maxlength="4" autocomplete="off" placeholder="4 digits"></div>
      <p class="demo">Demo student: Ravi K., PIN 1234. Five wrong PINs lock the profile for 5 minutes.</p>`;
    btn='Sign in as student';
  }else if(LG.step===0){
    form=`<div><label class="k" for="f0">Mobile number</label><input id="f0" class="in" type="tel" inputmode="numeric" autocomplete="off" value="${esc(LG.mobile)}" placeholder="10 digits"></div>
      <p class="demo">Demo number: ${r==='teacher'?'90000 00002':'90000 00003'}</p>`;
    btn='Send code';
  }else{
    form=`<div><label class="k" for="f1">One-time code sent to ${esc(LG.mobile)}</label><input id="f1" class="in" type="text" inputmode="numeric" maxlength="6" autocomplete="off" placeholder="6 digits"></div>
      ${LG.devCode?`<p class="demo">Demo code: ${esc(LG.devCode)}. A real deployment sends this by SMS.</p>`:''}
      <button type="button" class="back" data-a="lback">← Use a different number</button>`;
    btn='Sign in as '+r;
  }
  return `<div class="login"><div><h2>Sign in</h2><p class="sub">Each role sees only what it should. Sessions are signed tokens from the server; PINs and codes are stored hashed.</p></div>
    <div class="roles">${cards}</div>
    <form id="loginform" class="card" autocomplete="off">${form}${LG.err?`<p class="err" role="alert">${esc(LG.err)}</p>`:''}
      <button class="btn" type="submit"${LG.busy?' disabled':''}>${LG.busy?'Please wait…':btn}</button></form></div>`;
}
async function startSession(tok,pin){
  API.token=tok.access_token;SESS.save(tok);LG.err='';
  if(tok.role==='student'){
    if(pin)await DEV.remember(tok.user,pin,tok);
    PROFILE=LS.get('sahayak.p.'+tok.user.id)||blankProfile(tok.user);
    PROFILE.online=true;S.auth='student';S.sv='home';S.D=null;S.M=null;S.log=[];
    log(`Signed in as ${PROFILE.name}. Syllabus v${DATA.version||'bundle'} is on this phone.`);
    await refreshProfile();
  }else if(tok.role==='teacher'){S.auth='teacher';S.td=null;loadTeacher()}
  else{S.auth='parent';S.pn=null;S.pkids=[];loadParent()}
  render();
}
async function refreshProfile(){
  const p=PROFILE;if(!p||!canNet(p))return;
  try{await sync(p);const m=await API.get('/student/me');applyServer(p,m);p.syncErr=null;saveProfile()}
  catch(e){if(e.status===401)authLost()}
}
function authLost(){SESS.clear();API.token=null;S.auth=null;PROFILE=null;LG.err='Your session ended. Please sign in again.';render()}
function signOut(){SESS.clear();API.token=null;PROFILE=null;S.auth=null;S.td=null;S.pn=null;LG.err='';LG.step=0;LG.devCode='';render();loadDemoProfiles()}
document.addEventListener('submit',async e=>{
  if(e.target.id!=='loginform')return;
  e.preventDefault();if(LG.busy)return;
  const r=LG.role,v1=($('f1')||{}).value||'',v0=($('f0')||{}).value||'';
  LG.err='';LG.busy=true;render();
  try{
    if(r==='student'&&LG.creating){
      const d=LG.draft;d.name=($('nn')?$('nn').value:d.name).trim();const pin=($('np')||{}).value||'';
      if(!d.name)throw new Error('Please enter a name.');
      if(!/^\d{4}$/.test(pin))throw new Error('The PIN must be 4 digits.');
      const tok=await API.post('/auth/register-student',{name:d.name,pin,board:d.board,cls:d.cls,lang:d.lang});
      LG.creating=false;await startSession(tok,pin);
    }else if(r==='student'){
      if(!LG.pid)throw new Error('Pick a profile, or create one.');
      if(!/^\d{4}$/.test(v1.trim()))throw new Error('The PIN is 4 digits.');
      let tok=null,viaDevice=false;
      try{tok=await API.post('/auth/student/login',{student_id:LG.pid,pin:v1.trim()})}
      catch(err){
        if(!isOffline(err))throw err;
        const d=await DEV.check(LG.pid,v1.trim()).catch(()=>null);
        if(!d)throw new Error('You are offline, and this PIN does not match the one saved on this phone.');
        tok={access_token:d.token,role:'student',expires_in:Math.max(60,(d.exp-Date.now())/1000),user:d.user};
        viaDevice=true;
      }
      await startSession(tok,viaDevice?null:v1.trim());
      if(viaDevice)log('Signed in offline with the PIN saved on this phone.');
    }else if(LG.step===0){
      LG.mobile=v0.replace(/\D/g,'').slice(-10);
      if(LG.mobile.length!==10)throw new Error('Enter a 10-digit mobile number.');
      const o=await API.post('/auth/otp/request',{mobile:LG.mobile,role:r});
      LG.devCode=o.dev_code||'';LG.step=1;
    }else{
      const tok=await API.post('/auth/otp/verify',{mobile:LG.mobile,role:r,code:v1.trim()});
      LG.step=0;LG.devCode='';await startSession(tok,null);
    }
  }catch(err){LG.err=isOffline(err)?'No connection. Teachers and parents need to be online to sign in.':err.message}
  LG.busy=false;render();
});

/* ---------- Student ---------- */
const backBtn=(v,l)=>`<button class="back" data-a="nav" data-v="${v}">← ${l}</button>`;
const tname=(t,p)=>tn(t,p.lang);
function topBar(p){
  const U=UI[p.lang];
  return `<div class="bar"><span>${esc(p.name)} · Class ${p.cls} · ${esc(BNAME(p.board))}</span>
    <button class="pill ${p.online?'on':'off'}" data-a="net" aria-label="Toggle connection">${p.online?U.online:U.offline}${pending(p)?` · ${pending(p)} to send`:''}</button></div>`;
}
function weakPre(p,ch){
  const own=new Set(ch.topics);
  return uniq(ch.topics.flatMap(allPre)).filter(t=>!own.has(t)&&(p.P[t]??.5)<.6).sort((a,b)=>(p.P[a]??.5)-(p.P[b]??.5));
}
const measured=p=>Object.keys(p.P).length;
function homeView(p){
  const U=UI[p.lang],L=subjChapters(p),ex=exam(p),days=dayDiff(TODAY,pd(ex.date)),rd=readiness(p.P,ex.list);
  const hw=p.assignment?`<div class="banner"><b>Your teacher sent:</b> ${esc(p.assignment.text)}</div>`:'';
  const rows=L.map((ch,i)=>{
    const m=chMastery(p.P,ch),wp=weakPre(p,ch),inT=ex.list.some(x=>x.name===ch.name);
    return `<button class="crow" data-a="chapter" data-v="${i}"><span class="cname">${esc(ch.name)}${inT?'<span class="pill on">In the test</span>':''}</span>
      ${bar(m)}<span class="cpct">${Math.round(m*100)}%</span>
      ${wp.length?`<span class="note">Revisit first: ${esc(tname(wp[0],p))} ${pc(p.P[wp[0]]??.5)}</span>`:''}</button>`;
  }).join('');
  const chip=(a,v,l,on)=>`<button class="chip" data-a="${a}" data-v="${v}" aria-pressed="${on}">${l}</button>`;
  return `<div class="chips">${SUBJECTS.map(s=>chip('subj',s,s,p.subj===s)).join('')}${[['en','EN'],['te','తె'],['hi','हि']].map(([v,l])=>chip('plangs',v,l,p.lang===v)).join('')}</div>
    <p class="note">Today: ${fd(TODAY)}</p>${hw}
    ${measured(p)<12?`<div class="banner">New here? A 5-question placement check sets your starting picture.<div style="margin-top:8px"><button class="btn sm" data-a="diag">${U.placement}</button></div></div>`:`<button class="back" data-a="diag">${U.placement} again</button>`}
    <div class="lesson"><span class="kind">${esc(ex.name)} · ${esc(ex.by)}</span>
      <h3>${fd(pd(ex.date))}${days>0?` · in ${days} ${days===1?'day':'days'}`:''}</h3>
      <p class="note">${ex.list.map(c=>esc(c.name)).join(', ')}</p>
      <div class="rd"><span>You are ${Math.round(rd*100)}% ${U.ready}</span>${bar(rd)}</div>
      <button class="btn" data-a="nav" data-v="prep">${U.prep}</button></div>
    <h3>${U.chapters} · ${p.subj}</h3><div class="clist">${rows||'<p class="note">No chapters listed for this class.</p>'}</div>
    <p class="note">Chapter lists follow the ${esc(BNAME(p.board))} books and need a teacher’s check before use.</p>`;
}
function lessonCard(p,t,v){
  const L=T[t].lesson,n=p.exv[t]||0,alt=(n+(v||0))%2;
  return `<div class="lesson"><span class="kind">${alt?'Told as a story':'Explanation'} · ${esc(tname(t,p))} ${pc(p.P[t]??.5)}</span>
    <h3>${esc(L.title)}</h3>${alt?`<p>${esc(L.story)}</p>`:`<ul class="exs">${L.points.map(x=>`<li>${esc(x)}</li>`).join('')}</ul>`}</div>`;
}
function chapterView(p){
  const U=UI[p.lang],ch=subjChapters(p)[S.chi],wp=weakPre(p,ch);
  const ex=T[ch.topics[0]].lesson.example;
  const pre=wp.length?`<div class="banner">Before this chapter: ${esc(tname(wp[0],p))} is at ${pc(p.P[wp[0]]??.5)}. A short catch-up will make this chapter easier.
    <div style="margin-top:8px"><button class="btn sec sm" data-a="catchup" data-v="${wp[0]}">Catch up on ${esc(tname(wp[0],p))}</button></div></div>`:'';
  return `${backBtn('home',U.chapters)}<div><h2>${esc(ch.name)}</h2><div class="chips" style="margin-top:6px">${ch.topics.map(t=>`<span class="pill">${esc(tname(t,p))} ${pc(p.P[t]??.5)}</span>`).join('')}</div></div>
    ${pre}${ch.topics.slice(0,2).map(t=>lessonCard(p,t)).join('')}
    <button class="btn sec sm" data-a="xplain">${U.explain}</button>
    <div class="lesson"><span class="kind">Worked example · ${esc(tname(ch.topics[0],p))}</span><h3>${esc(ex.q)}</h3>
      <ol class="exs">${ex.steps.map(s=>`<li>${esc(s)}</li>`).join('')}</ol></div>
    <div class="two"><button class="btn" data-a="startp" data-v="${S.chi}">${U.practise}</button><button class="btn sec" data-a="startc" data-v="${S.chi}">${U.check}</button></div>`;
}
function diagView(p){
  const Dg=S.diag,q=Dg.qs[Dg.i],fb=Dg.fb;
  const opts=q.o.map((o,i)=>{let c='opt';if(fb){if(o.ok)c+=' right';else if(i===fb.picked)c+=' wrong'}return `<button class="${c}" data-a="dans" data-i="${i}"${fb?' disabled':''}>${esc(o.t)}</button>`}).join('');
  const f=fb?`<div class="fb ${fb.ok?'ok':'no'}"><b>${fb.ok?'Correct':'Not quite'}</b><span>${esc(fb.why)}</span></div><button class="btn" data-a="dnext">${Dg.i+1>=Dg.qs.length?'Finish':'Next'}</button>`:'';
  return `${backBtn('home','Skip for now')}<span class="kind">Placement check ${Dg.i+1} of ${Dg.qs.length} · ${esc(tname(q.t,p))}</span><div class="q">${esc(q.q)}</div><div class="opts">${opts}</div>${f}
    <p class="note">These questions are on the foundations behind your chapters. They set a starting picture. No marks.</p>`;
}

/* test and exam preparation */
function prepView(p){
  const U=UI[p.lang],ex=exam(p),pl=planFor(p,ex),rd=readiness(p.P,ex.list),term=p.prep.mode==='term';
  const chip=(v,l,on)=>`<button class="chip" data-a="pmode" data-v="${v}" aria-pressed="${on}">${l}</button>`;
  const rows=pl.items.map((it,i)=>`<li class="prow${i===0?' today':''}"><b>${i===0?U.today:fd(it.when)}</b>
    <span>${esc(it.title)}<br><span class="note">${esc(it.why)} · ${it.mins} min</span></span>
    ${i===0?'<span class="go"><button class="btn sm" data-a="plango">Start now</button></span>':''}</li>`).join('');
  const exRow=pl.days>0?`<li class="prow test"><b>${fd(pd(ex.date))}</b><span>${esc(ex.kind)}<br><span class="note">${ex.list.map(c=>esc(c.name)).join(', ')}</span></span></li>`:'';
  return `${backBtn('home',U.chapters)}<div><h2>Prepare for an exam</h2></div>
    <div class="chips">${chip('test','Class test',!term)}${chip('term','Half-yearly exam',term)}</div>
    <div class="lesson"><span class="kind">${esc(ex.by)}</span><h3>${esc(ex.name)}</h3>
      ${term?`<div><label class="k" for="termdate">Exam date</label><input id="termdate" class="in" type="date" min="${ds(addD(TODAY,1))}" max="${ds(addD(TODAY,30))}" value="${p.prep.term}"></div>`:`<p>${fd(pd(ex.date))}</p>`}
      <p class="note">${pl.days>0?`${pl.days} ${pl.days===1?'day':'days'} left`:'The date has passed'} · ${ex.list.length} ${ex.list.length===1?'chapter':'chapters'}</p>
      <div class="rd"><span>You are ${Math.round(rd*100)}% ${U.ready}</span>${bar(rd)}</div></div>
    <h3>Revision plan</h3><ul class="plan">${rows}${exRow}</ul>
    <p class="note">The plan counts back from the date, starts with weak basics from earlier classes, gives more days to weaker chapters, and ends with a mock test the day before. It changes as your mastery changes.</p>
    <button class="btn sec" data-a="mock">Take a mock test now</button>`;
}
function mockView(p){
  const K=S.M,it=K.items[K.i],total=K.items.reduce((a,x)=>a+x.marks,0);
  const left=Math.max(0,K.limit-Math.round((Date.now()-K.t0)/1000));
  const head=`${backBtn('prep','Plan')}<div class="bar"><span>Mock test · ${total} marks</span><span class="pill" id="clock">${left>0?fmtT(left)+' left':'Time is up'}</span></div>`;
  if(it.kind==='mcq')return `${head}<span class="kind">Question ${K.i+1} of ${K.items.length} · 1 mark · ${esc(tname(it.q.t,p))}</span><div class="q">${esc(it.q.q)}</div>
    <div class="opts">${it.q.o.map((o,j)=>`<button class="opt" data-a="mans" data-i="${j}">${esc(o.t)}</button>`).join('')}</div><p class="note">No hints in a mock. Answers are checked at the end.</p>`;
  const st=it.q.steps[K.si];
  return `${head}<span class="kind">Question ${K.i+1} of ${K.items.length} · 3 marks · step ${K.si+1} of ${it.q.steps.length}</span><div class="q">${esc(it.q.q)}</div>
    ${K.cur.length?`<div class="lesson">${K.cur.map((s,j)=>`<span class="note">Step ${j+1} · ${s.label}</span><span>${esc(s.picked)}</span>`).join('')}</div>`:''}
    <p><b>${esc(st.label)}</b> (1 mark): ${esc(st.prompt)}</p>
    <div class="opts">${st.o.map((o,j)=>`<button class="opt" data-a="mans" data-i="${j}">${esc(o.t)}</button>`).join('')}</div>
    <p class="note">Examiners give marks for each step, not only the final answer.</p>`;
}
function mockDoneView(p){
  const R=S.mres,rows=R.rows;
  const body=rows.map((r,i)=>{
    const cls=r.got===r.marks?'on':r.got?'':'off';let more='';
    if(r.kind==='mcq'&&r.got===0)more=`<span class="note">Your answer: ${esc(r.picked)}. Correct: ${esc(r.right)}. Slip: ${esc(r.m)}.</span>`;
    if(r.kind==='steps')more=`<span class="steps-res">${r.steps.map(s=>`<span class="${s.ok?'ok':'no'}">${s.ok?'✓':'✗'} ${esc(s.label)} ${s.ok?'1':'0'}/1${s.ok?'':` · should be: ${esc(s.right)}`}</span>`).join('')}</span>`;
    return `<div class="rrow"><b>Q${i+1}</b><span>${esc(r.q)}${more?'<br>'+more:''}</span><span class="pill ${cls}">${r.got}/${r.marks} · ${fmtT(r.secs)}</span></div>`;
  }).join('');
  const sr=rows.find(r=>r.kind==='steps');let advice='';
  if(sr&&sr.got<sr.marks){const [m,w,a]=sr.steps;
    advice=m.ok&&!w.ok&&a.ok?'You reached the right answer, but a working step was wrong. Examiners give marks per step, so this costs a mark even with the answer correct.'
      :!m.ok?'The first step is worth a mark. Decide your method before you calculate.':'Check each step before moving to the next one. Every step carries a mark.';
  }else if(sr)advice='Full marks on the step-wise question. In the exam, write every step the way you did here.';
  const slow=rows.map((r,i)=>({r,i})).sort((a,b)=>b.r.secs-a.r.secs)[0];
  const pace=slow.r.secs>slow.r.marks*90?`Q${slow.i+1} took ${fmtT(slow.r.secs)}, which is slow for ${slow.r.marks} ${slow.r.marks===1?'mark':'marks'}. A rough guide is about a minute per mark.`:`Pacing looks fine. The longest was Q${slow.i+1} at ${fmtT(slow.r.secs)}.`;
  const weak=uniq(rows.filter(r=>r.got<r.marks).map(r=>tname(r.t,p)));
  return `${backBtn('prep','Plan')}<div class="lesson"><span class="kind">Mock result</span><h3>${R.score} of ${R.total} marks</h3><p class="note">${fmtT(R.secs)} used of ${fmtT(R.limit)}</p></div>
    <div class="rlist">${body}</div>${advice?`<div class="banner">${advice}</div>`:''}<p class="note">${pace}</p>
    ${weak.length?`<div class="lesson"><span class="kind">Revise next</span><p>${weak.map(esc).join(', ')}</p></div>`:''}
    <p class="note">${SENDMSG(p)}</p>
    <div class="two"><button class="btn sec" data-a="mock">Another mock</button><button class="btn" data-a="nav" data-v="prep">Back to plan</button></div>`;
}

/* adaptive practice */
function lessonView(p){
  const D=S.D,t=D.learnFor,n=p.lessonN[t]||0,L=T[t].lesson,alt=n%2;
  const why=t===D.target?'A short refresher before we start.':`Your last mistake points to ${tname(t,p)}. A quick look first.`;
  return `<div class="lesson"><span class="kind">${alt?'Told as a story':'Explanation'}${n?' · different from last time':''} · ${esc(tname(t,p))}</span>
    <h3>${esc(L.title)}</h3>${alt?`<p>${esc(L.story)}</p>`:`<ul class="exs">${L.points.map(x=>`<li>${esc(x)}</li>`).join('')}</ul>`}
    <span class="note">Example: ${esc(L.example.q)}</span></div><p class="note">${why}</p>
    <button class="btn" data-a="learned">${UI[p.lang].start}</button>`;
}
function qView(p){
  const D=S.D,q=D.q,fb=D.fb;
  const opts=q.o.map((o,i)=>{let c='opt';if(fb){if(o.ok)c+=' right';else if(i===fb.picked)c+=' wrong'}return `<button class="${c}" data-a="ans" data-i="${i}"${fb?' disabled':''}>${esc(o.t)}</button>`}).join('');
  let f='';
  if(fb)f=`<div class="fb ${fb.ok?'ok':'no'}"><b>${fb.ok?'Correct':'Not quite'}</b><span>${esc(fb.why)}</span>
    ${!fb.ok&&fb.m?`<span><b>Likely slip:</b> ${esc(fb.m)}.</span>`:''}
    ${fb.pre?`<span>This slip usually comes from ${esc(tname(fb.pre,p))}. We will look at that first.</span>`:''}
    ${fb.back?'<span>Basics look steady. Back to the chapter.</span>':''}</div><button class="btn" data-a="next">${UI[p.lang].next}</button>`;
  const label=D.phase==='test'?`Check question ${D.testI+1} of ${D.testQ.length}`:`Question ${D.answered+(fb?0:1)}`;
  return `<span class="kind">${label} · ${esc(tname(q.t,p))}</span><div class="q">${esc(q.q)}</div><div class="opts">${opts}</div>${f}`;
}
function doneView(p){
  const D=S.D,s=D.testRes.filter(Boolean).length;
  const up=Object.keys(p.P).filter(t=>p.P[t]-(D.startP[t]??.5)>=.03).map(t=>`${tname(t,p)} ${pc(D.startP[t]??.5)} to ${pc(p.P[t])}`);
  const ts=D.ctopics,weakest=ts.slice().sort((a,b)=>(p.P[a]??.5)-(p.P[b]??.5))[0],wp=p.P[weakest]??.5;
  const tomorrow=wp>=.85?'A harder set, and you can help a classmate.':wp>=.6?`More mixed practice on ${tname(weakest,p)}.`:(allPre(weakest).length&&(p.P[weakestPre(p,weakest)]??.5)<.6?`A short revision of ${tname(weakestPre(p,weakest),p)} first.`:`More practice on ${tname(weakest,p)}.`);
  return `<div class="lesson"><span class="kind">Check result</span><h3>${s} of ${D.testQ.length} correct</h3><p>${up.length?up.slice(0,4).map(esc).join('. ')+'.':'Mastery stayed about the same.'}</p></div>
    <div class="lesson"><span class="kind">Next</span><p>${esc(tomorrow)}</p></div>
    <p class="note">${SENDMSG(p)}</p>
    <div class="two"><button class="btn sec" data-a="again">Practise again</button><button class="btn" data-a="nav" data-v="home">Back to chapters</button></div>`;
}
function paceTxt(p){
  const D=S.D;
  if(D.phase==='test')return 'Pace: checking what stuck';
  if(D.focus!==D.target)return 'Pace: slower, revisiting a basic';
  const r=D.recent.slice(-3);
  if(r.length===3&&r.every(Boolean)&&(p.P[D.target]??.5)>=.7)return 'Pace: faster, harder questions';
  return 'Pace: steady';
}
function practiceView(p){
  const D=S.D,U=UI[p.lang],ph=D.phase==='learn'?0:D.phase==='solve'?1:2;
  const body=D.phase==='learn'?lessonView(p):D.phase==='done'?doneView(p):qView(p);
  const tiles=uniq([...D.ctopics,D.focus]).slice(0,6);
  return `${backBtn('chapter','Chapter')}<span class="kind">${esc(D.ch)}</span>
    <div class="phases">${[U.learn,U.solve,U.test].map((t,i)=>`<span class="${i===ph?'on':''}">${t}</span>`).join('')}</div>
    <div class="path" aria-label="Mastery by topic">${tiles.map(t=>`<div class="${mc(p.P[t]??.5)}${t===D.focus&&D.phase!=='done'?' focus':''}"><b>${pc(p.P[t]??.5)}</b>${esc(tname(t,p))}</div>`).join('')}</div>
    <p class="note">${paceTxt(p)}</p>${body}`;
}
function phone(p){
  const v=S.sv;
  const body=v==='home'?homeView(p):v==='chapter'?chapterView(p):v==='prep'?prepView(p):v==='mock'?mockView(p):v==='mockdone'?mockDoneView(p):v==='diag'&&S.diag?diagView(p):v==='practice'&&S.D?practiceView(p):homeView(p);
  return topBar(p)+body;
}
function vStudent(){
  const p=me();if(!p)return '';
  const wait=pending(p);
  return `<div class="stage"><section class="phone" aria-label="Student phone">${phone(p)}</section>
    <section class="card"><h2>What the engine is doing</h2>
      <p class="note">The phone decides the next question on its own, even offline. It reads the kind of mistake, not just right or wrong, and follows it back through the prerequisite topics, even from earlier classes. Newest line is on top. Students would not see this panel.</p>
      <ul class="log">${S.log.map(l=>`<li>${esc(l)}</li>`).join('')||'<li>Waiting for the first answer.</li>'}</ul>
      <div class="legend"><span><i class="m-bad"></i>Below 45%</span><span><i class="m-warn"></i>45 to 69%</span><span><i class="m-good"></i>70% and above</span></div>
      <p class="note" id="outbox"><b>Outbox:</b> ${wait} ${wait===1?'item':'items'} waiting. Last sync: ${p.syncedAt?new Date(p.syncedAt).toLocaleTimeString('en-IN',{hour:'numeric',minute:'2-digit',second:'2-digit'}):'not yet'}${p.syncErr==='offline'?' (server not reachable, will retry)':''}.</p>
      <div style="display:flex;gap:8px;flex-wrap:wrap"><button class="btn sec sm" data-a="syncnow"${canNet(p)?'':' disabled'}>Sync now</button></div></section></div>`;
}

/* ---------- Teacher ---------- */
async function loadTeacher(quiet){
  if(!quiet){S.tload=true;render()}
  try{S.td=await API.get(`/teacher/class?board=${S.tb}&cls=${S.tc}&subject=${encodeURIComponent(S.ts)}`);S.terr=''}
  catch(e){S.terr=e.status===401?'':e.message;if(e.status===401)authLost()}
  S.tload=false;if(S.auth==='teacher')render();
}
const editing=()=>/^(INPUT|SELECT|TEXTAREA)$/.test((document.activeElement||{}).tagName||'');
setInterval(()=>{if(S.auth==='teacher'&&!editing()&&!S.tload)loadTeacher(true)},20000);
function vTeacher(){
  const b=S.tb,c=S.tc,s=S.ts,d=S.td;
  const sel=(id,opts,val)=>`<select id="${id}" class="in" style="width:auto;margin:0">${opts.map(([v,l])=>`<option value="${v}"${String(v)===String(val)?' selected':''}>${esc(l)}</option>`).join('')}</select>`;
  const selectors=`<div class="chips" style="align-items:center">${sel('tb',BOARDS.map(x=>[x,BNAME(x)]),b)}${sel('tc',[6,7,8,9,10].map(x=>[x,'Class '+x]),c)}${sel('ts',SUBJECTS.map(x=>[x,x]),s)}</div>`;
  if(!d||S.tload&&!d)return `<section class="card"><h2>Class view</h2>${selectors}<p class="note">${S.terr?esc(S.terr):'Loading the class…'}</p></section>`;
  if(d.empty||(d.scope&&(d.scope.board!==b||d.scope.cls!==c||d.scope.subject!==s)))return `<section class="card"><h2>Class view</h2>${selectors}<p class="note">${d.empty?'No students in this class yet.':'Loading the class…'}</p></section>`;
  const rows=d.rows,N=rows.length,t=d.test;
  const names=Object.fromEntries(rows.map(r=>[r.id,r.name]));
  const low=rows.filter(r=>r.test_ready<.6).length;
  const brief=`<ol class="brief">${d.briefing.items.map(x=>`<li>${esc(x.text)}</li>`).join('')}</ol>`;
  const byCh=S.heat==='chapter',cols=byCh?d.chapter_columns:d.topic_columns,key=byCh?'chapter_cells':'topic_cells';
  const body=rows.map(r=>`<tr class="${r.sample?'':'me'}"><td class="nm">${esc(r.name)}</td>${r[key].map(v=>`<td class="${mc(v)}">${Math.round(v*100)}</td>`).join('')}
    <td class="sy${r.stale?' stale':''}">${r.stale?'⚠ ':''}${esc(fmtSync(r.last_sync))}</td></tr>`).join('');
  const hchip=(v,l)=>`<button class="chip" data-a="heat" data-v="${v}" aria-pressed="${S.heat===v}">${l}</button>`;
  const heat=`<div class="chips">${hchip('topic','By topic')}${hchip('chapter','By chapter')}</div>
    <div class="scroll"><table><thead><tr><th>Student</th>${cols.map(x=>`<th>${esc(x.label)}</th>`).join('')}<th>Last sync</th></tr></thead><tbody>${body}</tbody></table></div>
    <div class="legend"><span><i class="m-bad"></i>Below 45</span><span><i class="m-warn"></i>45 to 69</span><span><i class="m-good"></i>70 and above</span><span>Mastery %. Columns marked C7 or C6 are earlier-class basics. Highlighted rows are real accounts; the others are sample classmates.</span></div>`;
  const grp=['extend','practise','basics'].map(k=>{const g=d.groups[k],mem=rows.filter(r=>r.group===k);
    return `<div class="grp"><h3>${esc(g.title)} <small>${mem.length} students</small></h3>
    <div class="who">${mem.map(r=>`<label>${esc(r.name)}<select data-sel="${r.id}" aria-label="Move ${esc(r.name)}">${['extend','practise','basics'].map(o=>`<option value="${o}"${o===k?' selected':''}>${esc(d.groups[o].title)}</option>`).join('')}</select></label>`).join('')||'<span class="note">No one right now</span>'}</div>
    <p class="note">${esc(g.action)}</p><div><button class="btn sec sm" data-a="hw" data-v="${k}"${mem.length?'':' disabled'}>Send practice to their phones</button></div></div>`}).join('');
  const sheets=`<div class="sheets">${d.worksheets.map(w=>`<div class="sheet"><b>Level ${w.level} · ${w.students} students</b><span>${esc(w.question)}</span><span class="note">${esc(w.note)}</span></div>`).join('')}</div>`;
  const tmr=ds(addD(TODAY,1)),mx=ds(addD(TODAY,90));
  const mocks=d.latest_mocks.map(m=>`${esc(m.name)}'s latest mock: ${m.score} of ${m.total}.`).join(' ');
  const testCard=`<section class="card"><h2>Class test</h2><p class="note">Set it once. Every student’s revision plan and every parent’s weekly note follow it.</p>
    <div><label class="k" for="tdate">Test date</label><input id="tdate" class="in" type="date" min="${tmr}" max="${mx}" value="${t.date}"></div>
    <div><label class="k">Chapters in the test</label><div class="chks">${t.available_chapters.map(n=>`<label><input type="checkbox" data-tch="${esc(n)}"${t.chapters.includes(n)?' checked':''}>${esc(n)}</label>`).join('')}</div></div>
    ${S.terr?`<p class="err" role="alert">${esc(S.terr)}</p>`:''}
    <p class="note">${low} of ${N} below 60% ready. ${mocks||'No mock result from a real profile has reached this dashboard yet.'}</p></section>`;
  const after=`<section class="card"><h2>After the test</h2><p class="note">The teacher enters marks or scans answer sheets. The briefing then targets the chapters that lost the most marks. Class averages below are from current mastery.</p>
    <div class="scroll"><table style="min-width:0"><thead><tr><th>Chapter</th><th>Class avg</th><th style="text-align:left">Most marks lost to</th></tr></thead><tbody>
    ${d.after_test.map(x=>`<tr><td class="nm">${esc(x.chapter)}</td><td class="${mc(x.class_avg)}">${Math.round(x.class_avg*100)}%</td><td class="sy">${esc(x.most_marks_lost_to)}</td></tr>`).join('')}</tbody></table></div></section>`;
  return `<div class="tgrid"><div style="display:flex;flex-direction:column;gap:16px;min-width:0">
      <section class="card"><h2>Class view</h2>${selectors}${heat}</section>
      <section class="card"><h2>Worksheets for tomorrow</h2><p class="note">Three levels instead of one sheet for 40 students. Students without a phone get the paper sheet, and the teacher scans it back in the morning.</p>${sheets}</section>${after}</div>
    <div style="display:flex;flex-direction:column;gap:16px;min-width:0">
      <section class="card"><h2>Morning briefing</h2>${brief}</section>${testCard}
      <section class="card"><h2>Suggested groups</h2><p class="note">The engine suggests. The teacher decides: move anyone with the menu beside their name.</p>${grp}${S.hwNote?`<p class="note">${esc(S.hwNote)}</p>`:''}</section></div></div>`;
}
async function saveTest(patch){
  const d=S.td;if(!d)return;
  const t=d.test,body={board:S.tb,cls:S.tc,subject:S.ts,name:t.name,date:t.date,chapters:t.chapters,...patch};
  try{await API.put('/teacher/test',body);S.terr=''}catch(e){S.terr=e.message}
  await loadTeacher(true);
}

/* ---------- Parent ---------- */
async function loadParent(){
  try{
    if(!S.pkids.length){S.pkids=await API.get('/parent/children');S.pk=S.pk||(S.pkids[0]&&S.pkids[0].id)}
    if(S.pk)S.pn=await API.get(`/parent/note?student_id=${S.pk}&lang=${S.pLang}`);
    S.perr='';
  }catch(e){S.perr=e.status===401?'':e.message;if(e.status===401)authLost()}
  if(S.auth==='parent')render();
}
function vParent(){
  const n=S.pn,lg=S.pLang;
  const chip=(v,l)=>`<button class="chip" data-a="plang" data-v="${v}" aria-pressed="${lg===v}">${l}</button>`;
  const kids=S.pkids.length>1?`<div class="chips">${S.pkids.map(x=>`<button class="chip" data-a="child" data-v="${x.id}" aria-pressed="${x.id===S.pk}">${esc(x.name)}</button>`).join('')}</div>`:'';
  if(!n)return `<div class="pstage"><section class="wa"><div class="wa-h"><span>Sahayak</span></div><p class="note">${S.perr?esc(S.perr):'Loading the weekly note…'}</p></section></div>`;
  const mins=n.minutes_by_day,mx=Math.max(15,...mins.map(m=>m.minutes));
  const bars=mins.map(m=>`<div class="${m.minutes?'':'zero'}"><span>${m.minutes}</span><i style="height:${Math.max(2,Math.round(m.minutes/mx*88))}px"></i><span>${WD[pd(m.date).getDay()].slice(0,2)}</span></div>`).join('');
  return `<div class="pstage"><section class="wa"><div class="wa-h"><span>Sahayak · ${esc(n.student.name)} · Class ${n.student.cls} ${esc(n.student.subject)}</span></div>${kids}
      <div class="chips">${chip('en','English')}${chip('te','తెలుగు')}${chip('hi','हिन्दी')}</div>
      <div class="bubble" lang="${lg}">${esc(n.text)}<span class="t">Preview of Sunday’s message</span></div>
      <p class="note">Based on the last sync: ${esc(fmtSync(n.last_sync))}.${lg!=='en'?' Hindi and Telugu text is a draft for review.':''}</p></section>
    <section class="card"><h2>Minutes of practice, last 7 days</h2><div class="bars" role="img" aria-label="Minutes practised each day">${bars}</div>
      <h3>What parents see</h3><p>A plain-language note in their own language, including the test date. No marks, no rank, and no other child’s name. The server only lets a parent read children linked to their own account.</p></section></div>`;
}

/* ---------- Shell ---------- */
function render(){
  const A=S.auth;
  const who=A==='student'&&PROFILE?PROFILE.name+' (student)':A==='teacher'?'Ms. Lakshmi (teacher)':A==='parent'?'Parent':'';
  $('me').innerHTML=A?`<span class="note">Signed in as ${esc(who)}</span><button class="btn sec sm" data-a="signout">Sign out</button>`:'';
  $('tabs').hidden=true;$('loop').hidden=true;$('try').hidden=!A;
  if(A)$('try').innerHTML=TRY[A];
  $('app').innerHTML=!A?vLogin():A==='student'?vStudent():A==='teacher'?vTeacher():vParent();
}
function planGo(){
  const p=me(),it=planFor(p,exam(p)).items[0];if(!it)return;
  if(it.kind==='mock')startMock();
  else if(it.kind==='catchup')startCatchup(it.t);
  else startPractice(Math.max(0,subjChapters(p).findIndex(c=>c.name===it.ch)));
}
document.addEventListener('click',e=>{
  const b=e.target.closest('[data-a]');if(!b||b.disabled)return;
  const a=b.dataset.a,v=b.dataset.v,p=me();
  if(a==='nav'){S.sv=v;if(v==='prep'){const pl=planFor(p,exam(p));log(`Revision plan built: ${pl.days} days to ${exam(p).name}, weak basics first.`)}}
  else if(a==='chapter'){S.chi=Number(v);S.sv='chapter'}
  else if(a==='subj'){p.subj=v;saveProfile();if(canNet(p))API.patch('/student/me',{subject:v}).catch(()=>{})}
  else if(a==='plangs'){p.lang=v;saveProfile();if(canNet(p))API.patch('/student/me',{lang:v}).catch(()=>{})}
  else if(a==='xplain'){const ch=subjChapters(p)[S.chi];ch.topics.forEach(t=>{p.exv[t]=(p.exv[t]||0)+1});log('Explanation re-told in a different way.')}
  else if(a==='startp')startPractice(Number(v));
  else if(a==='startc')startCheckFor(Number(v));
  else if(a==='catchup')startCatchup(v);
  else if(a==='learned')leaveLesson();
  else if(a==='ans')answer(Number(b.dataset.i));
  else if(a==='next')next();
  else if(a==='net')toggleNet();
  else if(a==='syncnow'){sync(p);return}
  else if(a==='again')startPractice(S.D.chi);
  else if(a==='pmode'){p.prep.mode=v;saveProfile()}
  else if(a==='plango')planGo();
  else if(a==='mock')startMock();
  else if(a==='mans')mockAnswer(Number(b.dataset.i));
  else if(a==='diag')startPlacement();
  else if(a==='dans')diagAnswer(Number(b.dataset.i));
  else if(a==='dnext')diagNext();
  else if(a==='heat')S.heat=v;
  else if(a==='lrole'){LG.role=v;LG.err='';LG.creating=false;LG.step=0;LG.devCode=''}
  else if(a==='lprofile'){LG.pid=Number(v);LG.err=''}
  else if(a==='lnew'){LG.creating=true;LG.err=''}
  else if(a==='lback'){LG.step=0;LG.devCode='';LG.err=''}
  else if(a==='dboard')LG.draft.board=v;
  else if(a==='dcls')LG.draft.cls=Number(v);
  else if(a==='dlang')LG.draft.lang=v;
  else if(a==='signout'){signOut();return}
  else if(a==='hw'){
    API.post('/teacher/assign',{board:S.tb,cls:S.tc,subject:S.ts,group:v}).then(r=>{S.hwNote='Sent: '+r.text;render()}).catch(err=>{S.terr=err.message;render()});return}
  else if(a==='plang'){S.pLang=v;loadParent();return}
  else if(a==='child'){S.pk=Number(v);loadParent();return}
  if(a==='dboard'||a==='dcls'||a==='dlang'){const nn=$('nn');if(nn)LG.draft.name=nn.value}
  render();
});
document.addEventListener('change',e=>{
  const el=e.target;
  if(el.dataset.sel){API.put('/teacher/group',{student_id:Number(el.dataset.sel),group:el.value}).then(()=>loadTeacher(true)).catch(err=>{S.terr=err.message;render()});return}
  else if(el.id==='tb'||el.id==='tc'||el.id==='ts'){
    if(el.id==='tb')S.tb=el.value;else if(el.id==='tc')S.tc=Number(el.value);else S.ts=el.value;
    S.td=null;loadTeacher();return}
  else if(el.id==='tdate'){if(el.value)saveTest({date:el.value});return}
  else if(el.id==='termdate'){const d=pd(el.value||''),n=dayDiff(TODAY,d);if(!isNaN(d)&&n>=1&&n<=90){me().prep.term=el.value;saveProfile()}else return}
  else if(el.dataset.tch){
    const set=new Set(S.td.test.chapters);el.checked?set.add(el.dataset.tch):set.delete(el.dataset.tch);
    const next=S.td.test.available_chapters.filter(n=>set.has(n));
    if(next.length)saveTest({chapters:next});else{el.checked=true}
    return}
  else return;
  render();
});
setInterval(()=>{
  const el=$('clock');if(!el||!S.M||S.sv!=='mock')return;
  const left=Math.max(0,S.M.limit-Math.round((Date.now()-S.M.t0)/1000));
  el.textContent=left>0?fmtT(left)+' left':'Time is up';
},1000);

/* ---------- start: reopen the saved session, else show sign-in ---------- */
(async function start(){
  const s=SESS.load();
  if(s){
    API.token=s.token;
    if(s.role==='student'){PROFILE=LS.get('sahayak.p.'+s.user.id)||blankProfile(s.user);S.auth='student';render();refreshProfile().then(render)}
    else if(s.role==='teacher'){S.auth='teacher';render();loadTeacher()}
    else{S.auth='parent';render();loadParent()}
  }else{render();loadDemoProfiles()}
})();
try{if('serviceWorker' in navigator&&location.protocol.startsWith('http'))navigator.serviceWorker.register('sw.js').catch(()=>{})}catch(e){}
