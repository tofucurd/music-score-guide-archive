import fs from 'node:fs';
import path from 'node:path';
import {spawn} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import {setTimeout as delay} from 'node:timers/promises';
import {connectCdp} from '../../revision-04/engineering/root-source-han-routing-working-01/src/cdp-transport.mjs';

const here=path.dirname(fileURLToPath(import.meta.url));
const root=path.resolve(here,'../../..');
const out=path.join(root,'output/score-sync-02/封面');
const profile=fs.mkdtempSync(path.join(here,'.cover-chrome-'));
const chrome=spawn('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',[
  '--headless','--remote-debugging-address=127.0.0.1','--remote-debugging-port=0',
  `--user-data-dir=${profile}`,'--no-first-run','--no-default-browser-check',
  '--disable-background-networking','--disable-extensions','--disable-sync',
  '--force-color-profile=srgb','about:blank'
],{stdio:'ignore'});
let client;
try {
  let endpoint;
  for(let i=0;i<200;i++){
    const f=path.join(profile,'DevToolsActivePort');
    if(fs.existsSync(f)){
      const [port,url]=fs.readFileSync(f,'utf8').split('\n');
      if(port&&url){endpoint=`ws://127.0.0.1:${port}${url}`;break;}
    }
    await delay(50);
  }
  if(!endpoint)throw Error('Chrome startup failed');
  client=await connectCdp({url:endpoint,timeoutMs:30000});
  const target=await client.send('Target.createTarget',{url:'about:blank'});
  const session=await client.send('Target.attachToTarget',{targetId:target.targetId,flatten:true});
  const send=(method,params={})=>client.send(method,params,{sessionId:session.sessionId});
  for(const [tag,width] of [['16x9',3840],['4x3',2880]]){
    const stem=path.join(out,`马勒第九交响曲-封面-${tag}`);
    await send('Emulation.setDeviceMetricsOverride',{width,height:2160,deviceScaleFactor:1,mobile:false});
    await send('Page.navigate',{url:'about:blank'});
    await send('Runtime.evaluate',{expression:`document.open();document.write(${JSON.stringify('<!doctype html><meta charset="utf-8"><style>html,body{margin:0;overflow:hidden}svg{display:block}</style>'+fs.readFileSync(stem+'.svg','utf8'))});document.close()`});
    await send('Runtime.evaluate',{expression:`Promise.all([document.fonts.load('300 760px CoverSerif'),document.fonts.load('500 224px CoverSerif'),document.fonts.load('400 65px CoverSerif')]).then(()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r))))`,awaitPromise:true});
    const shot=await send('Page.captureScreenshot',{format:'png',captureBeyondViewport:false,fromSurface:true});
    fs.writeFileSync(stem+'.png',Buffer.from(shot.data,'base64'));
    console.log(stem+'.png');
  }
} finally {
  try{await client?.send('Browser.close')}catch{}
  client?.close();
  if(chrome.exitCode===null)chrome.kill('SIGTERM');
  await delay(300);
  fs.rmSync(profile,{recursive:true,force:true,maxRetries:8,retryDelay:100});
}
