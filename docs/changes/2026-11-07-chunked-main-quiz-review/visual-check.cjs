const fs=require('node:fs');const path=require('node:path');const crypto=require('node:crypto');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE);
const out=path.resolve('runs/_chunked/261104_02');
const local=JSON.parse(fs.readFileSync(path.join(out,'local-review.json'),'utf8'));
const packet=JSON.parse(fs.readFileSync(path.join(out,'packet.json'),'utf8'));
const base='/api/root-learning/lectures/'+encodeURIComponent(packet.subject)+'/'+packet.runId;
async function api(url,body){const r=await fetch(local.api+url,body?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}:{});if(!r.ok)throw Error(r.status+' '+await r.text());return r.json();}
(async()=>{
 const created=await api(base+'/sessions',{requestId:'technical-visual-'+crypto.randomUUID()});
 const sid=created.sessionId;let view=await api('/api/root-learning/sessions/'+sid);let skipped=0;
 while(view.task&&!view.task.question.stimuli?.length){
  await api('/api/root-learning/sessions/'+sid+'/events',{requestId:crypto.randomUUID(),version:view.version,kind:'skip'});
  view=await api('/api/root-learning/sessions/'+sid);if(++skipped>100)throw Error('No visual task in normal session');
 }
 if(!view.task)throw Error('No prepared visual task');
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try{
  const page=await browser.newPage({viewport:{width:1280,height:960}});const errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.goto(process.env.PILOT_WEB_URL+'/bank/'+encodeURIComponent(packet.subject)+'/'+packet.runId);
  await page.getByRole('button',{name:'답만 보기',exact:true}).waitFor({timeout:30000});
  const images=page.locator('.main-quiz-solve img');await images.first().waitFor();
  const rendered=await images.evaluateAll(rows=>rows.map(i=>({src:i.src,loaded:i.complete&&i.naturalWidth>0})));
  if(rendered.length!==view.task.question.stimuli.length||rendered.some(i=>!i.loaded))throw Error('Actual stimuli not rendered');
  for(let i=0;i<rendered.length;i++){
   const image=await fetch(rendered[i].src);const bytes=Buffer.from(await image.arrayBuffer());
   if(crypto.createHash('sha256').update(bytes).digest('hex')!==view.task.question.stimuli[i].sha256)throw Error('Rendered image differs from reviewed bytes');
  }
  await page.screenshot({path:path.join(out,'image-question-desktop.png'),fullPage:true});
  await page.getByRole('button',{name:'답만 보기',exact:true}).click();
  const summary=page.locator('summary').filter({hasText:'출제 당시 원본 자료'});await summary.waitFor();await summary.click();
  const source=page.getByRole('link',{name:packet.sources[0].filename,exact:true});const href=await source.getAttribute('href');
  const pdf=await fetch(new URL(href,local.api));if(!pdf.ok)throw Error('Original source link failed');
  const digest=crypto.createHash('sha256').update(Buffer.from(await pdf.arrayBuffer())).digest('hex');
  if(digest!==packet.sources[0].sha256)throw Error('Linked original PDF differs');
  await page.setViewportSize({width:390,height:844});await page.screenshot({path:path.join(out,'image-answer-mobile.png'),fullPage:true});
  if(errors.length)throw Error(errors.join('\n'));
  fs.writeFileSync(path.join(out,'visual-check.json'),JSON.stringify({verified:true,technicalUser:'local-pilot',productionWrites:0,
   questionId:view.task.question.question_id,renderedImages:rendered.length,sourcePdfSha256:digest,sourceLinkVerified:true,jsErrors:errors},null,2));
  console.log('Actual image question + answer + identical source PDF verified in desktop/mobile UI; isolated technical account only');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
