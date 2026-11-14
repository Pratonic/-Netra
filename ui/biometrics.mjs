let ready;
export async function loadModels(){
 if(!ready)ready=(async()=>{
  if(!window.faceapi)throw Error('Recognition module is unavailable.');
  await Promise.resolve(faceapi.tf.setBackend('webgl')).catch(()=>faceapi.tf.setBackend('cpu'));
  await Promise.all([faceapi.nets.ssdMobilenetv1.loadFromUri('/models'),faceapi.nets.faceLandmark68Net.loadFromUri('/models'),faceapi.nets.faceRecognitionNet.loadFromUri('/models')]);
  const c=document.createElement('canvas');c.width=512;c.height=384;
  await faceapi.detectAllFaces(c,new faceapi.SsdMobilenetv1Options({minConfidence:.6}));
  await faceapi.nets.faceLandmark68Net.detectLandmarks(c);
  await faceapi.nets.faceRecognitionNet.computeFaceDescriptor(c);
 })();
 try{await ready;}catch(e){ready=null;throw e;}
}
export async function getCamera(video){
 if(!navigator.mediaDevices?.getUserMedia)throw Error('Camera requires HTTPS and browser permission.');
 const stream=await navigator.mediaDevices.getUserMedia({video:{width:{ideal:1280},height:{ideal:720},facingMode:'user'},audio:false});
 video.srcObject=stream;try{await video.play();return stream;}catch(e){stream.getTracks().forEach(t=>t.stop());throw e;}
}
export function stopCamera(stream){stream?.getTracks().forEach(t=>t.stop());}
function frame(source,max=960){
 const c=document.createElement('canvas'),width=source.videoWidth||source.naturalWidth||source.width,height=source.videoHeight||source.naturalHeight||source.height;
 if(!width||!height)throw Error('Camera has no usable frame.');
 const scale=Math.min(1,max/Math.max(width,height));c.width=Math.round(width*scale);c.height=Math.round(height*scale);
 c.getContext('2d',{willReadFrequently:true}).drawImage(source,0,0,c.width,c.height);return c;
}
// Quality depends on retained face pixels, not a percentage of the field of view.
// Full landmarks align the face chip before its descriptor, including face roll.
export function usableFace(face,width,height,minPixels=80){
 const b=face.detection.box;
 return face.detection.score>=.7&&Math.min(b.width,b.height)>=minPixels&&b.x>=2&&b.y>=2&&b.x+b.width<=width-2&&b.y+b.height<=height-2;
}
const detect=c=>faceapi.detectAllFaces(c,new faceapi.SsdMobilenetv1Options({minConfidence:.6})).withFaceLandmarks().withFaceDescriptors();
export async function captureReference(source){
 await loadModels();const c=frame(source,1280),faces=await detect(c);
 if(faces.length!==1)throw Error(faces.length?'Only one person may be enrolled at a time.':'No clear face found. Face the camera in good light.');
 const face=faces[0];if(!usableFace(face,c.width,c.height,100))throw Error('Keep your whole face in view with good lighting. Move a little closer if it looks small.');
 const b=face.detection.box,side=Math.min(Math.max(b.width,b.height)*1.5,c.width,c.height),x=Math.max(0,Math.min(c.width-side,b.x+b.width/2-side/2)),y=Math.max(0,Math.min(c.height-side,b.y+b.height/2-side/2));
 const photo=document.createElement('canvas');photo.width=320;photo.height=320;photo.getContext('2d').drawImage(c,x,y,side,side,0,0,320,320);
 return{photo:photo.toDataURL('image/jpeg',.9),descriptors:[Array.from(face.descriptor)]};
}
export function closest(descriptor,people){return people.filter(p=>p.descriptors?.length).map(p=>({person:p,distance:Math.min(...p.descriptors.map(d=>Math.hypot(...d.map((n,i)=>n-descriptor[i]))))})).sort((a,b)=>a.distance-b.distance);}
export function confidentMatch(rankings){return !!rankings.length&&rankings[0].distance<=.48&&(rankings.length===1||rankings[1].distance-rankings[0].distance>=.08);}
export async function recognize(video,people,onProgress=()=>{}){
 const started=performance.now();let ended=false,last=null,identity=null,samples=0,multiple=false,qualityReason='No clear face found. Keep your whole face in view.';
 return new Promise(resolve=>{
  const finish=()=>{
   if(ended)return;ended=true;clearTimeout(timer);const elapsed=performance.now()-started;
   const strong=elapsed<=2000&&!multiple&&samples>=2&&last&&confidentMatch(last);
   resolve({person:strong?last[0].person:null,elapsed,samples,matchDistance:strong?last[0].distance:null,outcome:multiple?'deny':strong?'matched':'stepup',reason:multiple?'One person at a time, please.':strong?'Identity found.':qualityReason});
  };
  const timer=setTimeout(finish,1980);
  (async()=>{try{
   while(!ended){
    const c=frame(video),faces=await detect(c);if(ended)return;
    onProgress(Math.min(1,(performance.now()-started)/2000));
    if(faces.length>1){multiple=true;finish();return;}
    if(faces.length===1&&usableFace(faces[0],c.width,c.height)){
     const rankings=closest(Array.from(faces[0].descriptor),people);
     if(confidentMatch(rankings)){
      if(identity!==rankings[0].person.id){identity=rankings[0].person.id;samples=0;}
      samples++;last=rankings;if(samples>=2){finish();return;}
     }else{identity=null;samples=0;last=null;qualityReason='No confident identity match. Try again or ask an attendant.';}
    }else{identity=null;samples=0;last=null;qualityReason=faces.length?'Keep your whole face visible in good light. Move slightly closer if needed.':'No clear face found. Keep your whole face in view.';}
    await new Promise(r=>setTimeout(r,30));
   }
  }catch{qualityReason='Camera check could not finish. Try again or ask an attendant.';finish();}})();
 });
}
