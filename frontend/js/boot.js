'use strict';
/* Load the syllabus (from the server, else the copy cached on this phone), then start the engine and the app. */
(async()=>{
  let data=null;
  try{const r=await fetch('/api/content/bundle');if(r.ok){data=await r.json();try{localStorage.setItem('sahayak.bundle',JSON.stringify(data))}catch(e){}}}catch(e){}
  if(!data){try{data=JSON.parse(localStorage.getItem('sahayak.bundle'))}catch(e){}}
  if(!data){document.getElementById('app').innerHTML='<p class="err" role="alert">Could not load the syllabus. Connect once so it can be saved on this phone.</p>';return}
  window.DATA=data;
  for(const src of ['js/api.js','js/engine.js','js/app.js'])await new Promise((ok,no)=>{const s=document.createElement('script');s.src=src;s.onload=ok;s.onerror=no;document.body.appendChild(s)});
})();
