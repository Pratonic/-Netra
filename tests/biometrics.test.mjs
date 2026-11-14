import test from 'node:test';
import assert from 'node:assert/strict';
import {usableFace,closest,confidentMatch,recognize} from '../ui/biometrics.mjs';
const face=(width=90,score=.9)=>({detection:{score,box:{x:100,y:100,width,height:100}},descriptor:new Float32Array(128)});
test('small face is usable without filling twenty percent of the frame',()=>{
 assert.equal(usableFace(face(),960,720),true);
 assert.equal(usableFace(face(60),960,720),false);
 assert.equal(usableFace(face(90,.6),960,720),false);
});
test('clipped faces stay unusable',()=>{const f=face();f.detection.box.x=-5;assert.equal(usableFace(f,960,720),false);});
test('additional enrolled view can match without relaxing the threshold',()=>{
 const people=[{id:'a',descriptors:[Array(128).fill(.1),Array(128).fill(.01)]},{id:'b',descriptors:[Array(128).fill(.2)]}];
 const ranked=closest(Array(128).fill(0),people);assert.equal(ranked[0].person.id,'a');assert.equal(confidentMatch(ranked),true);
 assert.equal(confidentMatch([{distance:.481}]),false);assert.equal(confidentMatch([{distance:.3},{distance:.35}]),false);
});
// Exercise the asynchronous recognition decision, with deterministic detector output.
// These tests check matching/timing policy, not model accuracy or physical pose tolerance.
globalThis.document={createElement:()=>({getContext:()=>({drawImage(){}})})};
const people=[{id:'a',descriptors:[Array(128).fill(0)]}];
let sequence=[],delay=0;
globalThis.faceapi={SsdMobilenetv1Options:class {},detectAllFaces(){return {withFaceLandmarks(){return {async withFaceDescriptors(){if(delay)await new Promise(r=>setTimeout(r,delay));return sequence.shift()||[];}};}};}};
test('two consecutive clear frames identify the person',async()=>{
 sequence=[[face()],[face()]];delay=0;const r=await recognize({width:960,height:720},people);assert.equal(r.person.id,'a');assert.equal(r.samples,2);assert.ok(r.elapsed<2000);
});
test('multiple faces never produce an identity',async()=>{
 sequence=[[face(),face()]];const r=await recognize({width:960,height:720},people);assert.equal(r.outcome,'deny');assert.equal(r.person,null);
});
test('one good frame and then unusable frames cannot identify',async()=>{
 sequence=[[face()],[face(60)]];const r=await recognize({width:960,height:720},people);assert.equal(r.person,null);assert.equal(r.outcome,'stepup');
});
test('slow inference never silently becomes a successful match',async()=>{
 sequence=[[face()],[face()]];delay=2100;const r=await recognize({width:960,height:720},people);assert.equal(r.person,null);assert.equal(r.outcome,'stepup');assert.ok(r.elapsed<2100);delay=0;
});
import {parseLine,summarize} from '../ui/sensor.mjs';
test('sensor lines parse and reject garbage',()=>{
 assert.deepEqual(parseLine('{"t":"ir","present":1,"raw":612,"ms":5,"n":"ab"}'),{present:true,raw:612,ms:5,n:'ab'});
 assert.equal(parseLine('{"t":"hello","id":"trinetra-esp8266"}').hello,'trinetra-esp8266');
 assert.equal(parseLine('not json'),null);
 assert.equal(parseLine('{"t":"ir","present":2,"raw":1}'),null);
});
test('sensor summary counts only fresh readings for the current nonce',()=>{
 const list=[{present:false,raw:10,at:0,n:'old'},...Array.from({length:10},(_,i)=>({present:i<8,raw:600+i,at:1000+i*50,n:'new'}))];
 const s=summarize(list,1500,{windowMs:2500,nonce:'new'});
 assert.equal(s.status,'ok');assert.equal(s.samples,10);assert.equal(s.presentRatio,.8);assert.equal(s.rawMedian,605);assert.equal(s.ageMs,50);
 assert.equal(summarize(list,9000,{windowMs:1000,nonce:'new'}).status,'stale');
});
