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
  get(p){return API.call('GET',p)},post(p,b){return API.call('POST',p,b)},put(p,b){return API.call('PUT',p,b)},patch(p,b){return API.call('PATCH',p,b)}
};
const isOffline=e=>!e.status;

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
  remember(u,pin,tok){
    return DEV.hash(pin).then(h=>{
      const l=DEV.list().filter(x=>x.id!==u.id);
      l.push({id:u.id,name:u.name,cls:u.cls,board:u.board,h,token:tok.access_token,exp:Date.now()+tok.expires_in*1000,user:u});
      LS.set(DEV.key,l);
    }).catch(()=>{});
  },
  async hash(pin,salt){
    if(!(window.crypto&&crypto.subtle))throw new Error('no webcrypto');
    const s=salt||Array.from(crypto.getRandomValues(new Uint8Array(12)),b=>b.toString(16).padStart(2,'0')).join('');
    const k=await crypto.subtle.importKey('raw',new TextEncoder().encode(pin),'PBKDF2',false,['deriveBits']);
    const bits=await crypto.subtle.deriveBits({name:'PBKDF2',salt:new TextEncoder().encode(s),iterations:100000,hash:'SHA-256'},k,256);
    return s+'$'+Array.from(new Uint8Array(bits),b=>b.toString(16).padStart(2,'0')).join('');
  },
  async check(id,pin){
    const d=DEV.list().find(x=>x.id===id);if(!d)return null;
    const [salt]=d.h.split('$');
    return (await DEV.hash(pin,salt))===d.h?d:null;
  }
};
