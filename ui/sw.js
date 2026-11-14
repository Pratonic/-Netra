const CACHE='aegis-shell-v4';
const SHELL=['/','/style.css?v=4','/app.mjs?v=4','/offline.mjs','/biometrics.mjs','/vendor/face-api.min.js'];
self.addEventListener('install',event=>{event.waitUntil(caches.open(CACHE).then(cache=>cache.addAll(SHELL)).then(()=>self.skipWaiting()));});
self.addEventListener('activate',event=>{event.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(k=>k.startsWith('aegis-shell-')&&k!==CACHE).map(k=>caches.delete(k)))).then(()=>self.clients.claim()));});
self.addEventListener('fetch',event=>{
 const url=new URL(event.request.url);
 if(event.request.method!=='GET'||url.origin!==self.location.origin||url.pathname.startsWith('/api/'))return;
 const isStatic=SHELL.some(path=>new URL(path,self.location.origin).pathname===url.pathname)||url.pathname.startsWith('/models/')||url.pathname==='/liveness.mjs'||url.pathname==='/liveness.css';
 if(!isStatic&&event.request.mode!=='navigate')return;
 event.respondWith((async()=>{try{const response=await fetch(event.request);if(response.ok&&response.type!=='opaqueredirect'){const cache=await caches.open(CACHE);await cache.put(event.request,response.clone());}return response;}catch{const cached=await caches.match(event.request,{ignoreSearch:true});if(cached)return cached;if(event.request.mode==='navigate')return caches.match('/');return new Response('Unavailable offline',{status:503});}})());
});
