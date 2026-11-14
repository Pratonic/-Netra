import {build} from 'esbuild';
import fs from 'node:fs/promises';
import path from 'node:path';
import {spawnSync} from 'node:child_process';
import {createHash} from 'node:crypto';
const root=process.cwd(),publicDir=path.join(root,'backend/public');
await fs.mkdir(publicDir,{recursive:true});
for(const file of ['index.html','style.css','app.mjs','biometrics.mjs','offline.mjs','sw.js'])await fs.copyFile(path.join(root,'ui',file),path.join(publicDir,file));
const digest=createHash('sha256');
for(const file of ['index.html','style.css','app.mjs','biometrics.mjs','offline.mjs','sw.js'])digest.update(await fs.readFile(path.join(root,'ui',file)));
const revision=digest.digest('hex').slice(0,12);
for(const file of ['index.html','sw.js']){const p=path.join(publicDir,file);const text=await fs.readFile(p,'utf8');await fs.writeFile(p,text.replaceAll('?v=4','?v='+revision).replaceAll('aegis-shell-v4','aegis-shell-'+revision));}
for(const dir of ['models','vendor'])await fs.cp(path.join(root,'assets',dir),path.join(publicDir,dir),{recursive:true});
await build({entryPoints:['ui/liveness.jsx'],bundle:true,outfile:path.join(publicDir,'liveness.mjs'),format:'esm',platform:'browser',target:'es2022',minify:true,define:{'process.env.NODE_ENV':'"production"'},loader:{'.svg':'dataurl','.png':'dataurl'}});
await fs.mkdir('dist/server',{recursive:true});await fs.copyFile('worker/index.js','dist/server/index.js');
const check=spawnSync('python',['-m','py_compile','backend/service.py','backend/policy.py'],{stdio:'inherit'});if(check.status!==0)process.exit(check.status||1);
console.log('Built AWS application assets and Sites gateway.');
