// Web Serial bridge to the त्रिNetra kiosk sensor (hardware/trinetra_sensor).
// The board streams newline-delimited JSON IR readings at ~20 Hz and accepts LED commands.
// Sensor evidence is advisory: it can lower a decision on the server, never raise one.
const BAUD=115200,KEEP_MS=4000,PRESENT_STABLE_MS=400,ABSENT_STABLE_MS=800;
const LED={allow:'ALLOW',deny:'DENY',stepup:'STEPUP',offline:'OFFLINE',scan:'SCAN',idle:'IDLE'};
let port=null,reader=null,writer=null,readings=[],state='disconnected',deviceId='',nonce='',lastLed='IDLE';
let presence=false,candidate=false,candidateSince=0,watching=false;
const listeners=new Set(),encoder=new TextEncoder();

export const sensorSupported=()=>typeof navigator!=='undefined'&&'serial' in navigator;
export function onSensor(fn){listeners.add(fn);return()=>listeners.delete(fn);}
export function sensorInfo(){return{state,deviceId,present:presence};}
const emit=event=>{for(const fn of listeners){try{fn(event);}catch{}}};
const setState=next=>{if(state!==next){state=next;emit({type:'state',state});}};
const setPresence=next=>{if(presence!==next){presence=next;emit({type:'presence',present:next});}};

export function parseLine(text){
 try{
  const m=JSON.parse(text);
  if(m?.t==='ir'&&(m.present===0||m.present===1)&&Number.isFinite(m.raw))return{present:m.present===1,raw:m.raw,ms:Number(m.ms)||0,n:typeof m.n==='string'?m.n:''};
  if(m?.t==='hello')return{hello:String(m.id||'unknown').slice(0,40)};
 }catch{}
 return null;
}

// Summarize recent readings into the evidence the backend evaluates.
export function summarize(list,now,{windowMs=1000,nonce:want=''}={}){
 const recent=list.filter(r=>now-r.at<=windowMs&&now>=r.at&&(!want||r.n===want));
 if(!recent.length)return{status:'stale',samples:0,ageMs:list.length?Math.round(now-list[list.length-1].at):null};
 const raws=recent.map(r=>r.raw).sort((a,b)=>a-b);
 return{status:'ok',samples:recent.length,presentRatio:+(recent.filter(r=>r.present).length/recent.length).toFixed(2),rawMedian:raws[raws.length>>1],ageMs:Math.round(now-recent[recent.length-1].at)};
}

function handleLine(text){
 const m=parseLine(text);if(!m)return;
 if(m.hello!==undefined){deviceId=m.hello;emit({type:'hello',id:deviceId});return;}
 const at=performance.now();readings.push({...m,at});
 while(readings.length&&at-readings[0].at>KEEP_MS)readings.shift();
 if(m.present!==candidate){candidate=m.present;candidateSince=at;}
 if(candidate!==presence&&at-candidateSince>=(candidate?PRESENT_STABLE_MS:ABSENT_STABLE_MS))setPresence(candidate);
}

async function readLoop(p){
 const decoder=new TextDecoder();let buffer='';
 while(port===p&&p.readable){
  reader=p.readable.getReader();
  try{
   for(;;){
    const {value,done}=await reader.read();if(done)break;
    buffer+=decoder.decode(value,{stream:true});let i;
    while((i=buffer.indexOf('\n'))>=0){handleLine(buffer.slice(0,i).trim());buffer=buffer.slice(i+1);}
    if(buffer.length>512)buffer='';
   }
  }catch{/* framing error or unplugged; loop re-checks readable */}
  finally{try{reader.releaseLock();}catch{}reader=null;}
 }
 try{writer?.releaseLock();}catch{}
 writer=null;try{await p.close();}catch{}
 if(port===p)port=null;
 readings=[];candidate=false;setPresence(false);setState('disconnected');
}

async function send(text){if(!writer)return;try{await writer.write(encoder.encode(text+'\n'));}catch{}}

export async function connectSensor({prompt=true}={}){
 if(!sensorSupported())throw Error('Web Serial needs Chrome or Edge on a desktop.');
 if(port)return true;
 const known=await navigator.serial.getPorts();
 const p=known[0]||(prompt?await navigator.serial.requestPort():null);
 if(!p)return false;
 setState('connecting');
 try{await p.open({baudRate:BAUD});}
 catch(e){setState('disconnected');throw Error(e?.name==='InvalidStateError'?'Sensor port is already open in another program. Close the Arduino Serial Monitor.':'Could not open the sensor port. Close other serial programs and try again.');}
 port=p;writer=p.writable.getWriter();setState('connected');
 readLoop(p);
 await send('HELLO');await send(lastLed);if(nonce)await send('N '+nonce);
 return true;
}

export async function disconnectSensor(){const r=reader;port=null;try{await r?.cancel();}catch{}}

// Reconnect to previously granted ports without prompting, and when the board is plugged back in.
export function watchSensor(){
 if(watching||!sensorSupported())return;watching=true;
 navigator.serial.addEventListener('connect',()=>{connectSensor({prompt:false}).catch(()=>{});});
 connectSensor({prompt:false}).catch(()=>{});
}

export function setLed(name){lastLed=LED[name]||'IDLE';send(lastLed);}

// Start a fresh measurement window: readings are only counted once they echo this nonce.
export function beginReading(){
 nonce=Array.from(crypto.getRandomValues(new Uint8Array(4)),b=>b.toString(16).padStart(2,'0')).join('');
 send('N '+nonce);return nonce;
}

export function sensorSnapshot(windowMs=2500){
 if(!port||state!=='connected')return{status:'disconnected'};
 return summarize(readings,performance.now(),{windowMs,nonce});
}
