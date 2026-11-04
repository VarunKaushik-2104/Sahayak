'use strict';
/* Thin client for the Sahayak API. Same origin, bearer token. A network failure throws an error with no .status. */
const API={
  token:null,
  async call(method,path,body){
    const r=await fetch('/api'+path,{method,headers:{'Content-Type':'application/json',...(API.token?{Authorization:'Bearer '+API.token}:{})},body:body===undefined?undefined:JSON.stringify(body)});
    let data=null;try{data=await r.json()}catch(e){}
    if(!r.ok){
      const d=data&&data.detail;
      const err=new Error(typeof d==='string'?d:'Please check what you entered and try again.');
      err.status=r.status;throw err;
    }
    return data;
  },
  get(p){return API.call('GET',p)},post(p,b){return API.call('POST',p,b)},put(p,b){return API.call('PUT',p,b)},patch(p,b){return API.call('PATCH',p,b)},del(p){return API.call('DELETE',p)}
};
const isOffline=e=>!e.status;
/* kept in memory only, never stored: lets the app renew an expired session without asking for the PIN again */
async function relogin(){
  if(!API.pin||!API.uid)return false;
  try{const tok=await API.post('/auth/student/login',{student_id:API.uid,pin:API.pin});API.token=tok.access_token;SESS.save(tok);DEV.remember(tok.user,API.pin,tok);return true}
  catch(e){return false}
}

/* the signed-in account, kept on this device so the app opens straight back in, even with no network */
const SESS={
  key:'sahayak.session',
  save(tok){LS.set(SESS.key,{token:tok.access_token,role:tok.role,user:tok.user,exp:Date.now()+tok.expires_in*1000})},
  load(){const s=LS.get(SESS.key);return s&&s.exp>Date.now()?s:null},
  clear(){LS.del(SESS.key)}
};

/* offline sign-in for a shared phone: after one online sign-in, the PIN is checked against a salted hash kept on the device */
const DEV={
  key:'sahayak.devices',
  list(){return LS.get(DEV.key)||[]},
  forget(id){LS.set(DEV.key,DEV.list().filter(x=>x.id!==id));LS.del('sahayak.p.'+id)},
  remember(u,pin,tok){
    return DEV.hash(pin).then(h=>{
      const l=DEV.list().filter(x=>x.id!==u.id);
      l.push({id:u.id,name:u.name,cls:u.cls,board:u.board,h,token:tok.access_token,exp:Date.now()+tok.expires_in*1000,user:u});
      LS.set(DEV.key,l);
    }).catch(()=>{});
  },
  /* WebCrypto only exists on https or localhost. On a plain http address (a phone on the home network) fall back to an iterated SHA-256 written in JS.
     Either way the PIN is only checked against a salted hash kept on this device. */
  async hash(pin,salt){
    const s=salt||Array.from((window.crypto&&crypto.getRandomValues?crypto.getRandomValues(new Uint8Array(12)):Array.from({length:12},()=>Math.floor(Math.random()*256))),b=>b.toString(16).padStart(2,'0')).join('');
    const hex=a=>Array.from(a,b=>b.toString(16).padStart(2,'0')).join('');
    if(window.crypto&&crypto.subtle){
      const k=await crypto.subtle.importKey('raw',new TextEncoder().encode(pin),'PBKDF2',false,['deriveBits']);
      const bits=await crypto.subtle.deriveBits({name:'PBKDF2',salt:new TextEncoder().encode(s),iterations:100000,hash:'SHA-256'},k,256);
      return 'p$'+s+'$'+hex(new Uint8Array(bits));
    }
    let d=new TextEncoder().encode(s+':'+pin);
    for(let i=0;i<20000;i++)d=sha256(d);
    return 'j$'+s+'$'+hex(d);
  },
  async check(id,pin){
    const d=DEV.list().find(x=>x.id===id);if(!d)return null;
    const parts=d.h.split('$'),legacy=parts.length===2;      // older saved hashes had no prefix
    const salt=legacy?parts[0]:parts[1],stored=legacy?'p$'+d.h:d.h;
    return (await DEV.hash(pin,salt))===stored?d:null;
  }
};

/* compact SHA-256 (fallback for non-secure pages) */
function sha256(m){
  const K=new Uint32Array([0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2]);
  const H=new Uint32Array([0x6a09e667,0xbb67ae85,0x3c6ef372,0xa54ff53a,0x510e527f,0x9b05688c,0x1f83d9ab,0x5be0cd19]);
  const l=m.length,n=((l+9+63)>>6)<<6,b=new Uint8Array(n);b.set(m);b[l]=0x80;
  const dv=new DataView(b.buffer);dv.setUint32(n-4,(l*8)>>>0);dv.setUint32(n-8,Math.floor(l*8/4294967296));
  const w=new Uint32Array(64),rr=(x,c)=>(x>>>c)|(x<<(32-c));
  for(let o=0;o<n;o+=64){
    for(let i=0;i<16;i++)w[i]=dv.getUint32(o+i*4);
    for(let i=16;i<64;i++){const a=rr(w[i-15],7)^rr(w[i-15],18)^(w[i-15]>>>3),c=rr(w[i-2],17)^rr(w[i-2],19)^(w[i-2]>>>10);w[i]=(w[i-16]+a+w[i-7]+c)>>>0}
    let [a,c,d,e,f,g,h,i2]=H;
    for(let i=0;i<64;i++){const t1=(i2+(rr(f,6)^rr(f,11)^rr(f,25))+((f&g)^(~f&h))+K[i]+w[i])>>>0,t2=((rr(a,2)^rr(a,13)^rr(a,22))+((a&c)^(a&d)^(c&d)))>>>0;i2=h;h=g;g=f;f=(e+t1)>>>0;e=d;d=c;c=a;a=(t1+t2)>>>0}
    H[0]+=a;H[1]+=c;H[2]+=d;H[3]+=e;H[4]+=f;H[5]+=g;H[6]+=h;H[7]+=i2;
  }
  const out=new Uint8Array(32),ov=new DataView(out.buffer);H.forEach((v,i)=>ov.setUint32(i*4,v));return out;
}
