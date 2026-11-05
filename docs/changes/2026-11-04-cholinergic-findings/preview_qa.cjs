const fs=require('node:fs');
const crypto=require('node:crypto');
const {pathToFileURL}=require('node:url');
const {chromium}=require('C:/Users/ows01/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const base='C:/Users/ows01/Documents/Python Scripts/Study_EZ_Open/runs/_examples/cholinergic-findings-20261104';
const vis='C:/Users/ows01/.codex/visualizations/2026/11/03/01a19f97-9412-7273-bf02-f60649c4c87c';
const result=JSON.parse(fs.readFileSync(base+'/result.json','utf8'));
const hash=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
const assert=(x,s)=>{if(!x)throw Error(s);};
(async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 const page=await browser.newPage({viewport:{width:800,height:1100}});const errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 await page.goto(pathToFileURL(vis+'/cholinergic-corrected-check.html').href);
 const frame=page.frameLocator('iframe');
 const root=frame.locator('#cholinergic-corrected-1104');await root.waitFor();
 assert(await root.locator('.ct-question-select option').count()===result.bank.questions.length,'Missing full question browser');
 assert(await root.locator('[data-concept]').count()>=result.brief.concepts.length,'Missing concept nodes');
 for(const c of result.brief.concepts){
  await root.locator(`[data-concept="${c.concept_id}"]`).first().click();
  assert((await root.locator('.ct-selected-title').innerText())===c.label,'Concept selection mismatch '+c.concept_id);
 }
 const d=result.resolution.directions.find(d=>d.question_ids.length);
 assert(Boolean(d),'No actual corrected direction question');
 const q=result.bank.questions.find(q=>q.question_id===d.question_ids[0]);
 await root.locator('.ct-original-directions').getByRole('button',{name:q.question_id+' 문항 보기',exact:true}).first().click();
 assert((await root.locator('.ct-qtext').innerText())===q.question,'Displayed stem changed');
 assert(await root.locator('#ct-answer-1104').isHidden(),'Answer should start hidden');
 await root.locator('.ct-reveal').click();
 assert((await root.locator('.ct-answer').innerText())===q.answer,'Displayed answer changed');
 assert((await root.locator('.ct-explanation').innerText())===q.explanation,'Displayed explanation changed');
 const cloze=result.bank.questions.find(q=>q.format==='cloze');
 if(cloze){
  await root.locator('.ct-question-select').selectOption(cloze.question_id);
  const text=await root.locator('.ct-qtext').innerText();
  assert(!/[{}]/.test(text)&&/\[ \d+ \]/.test(text),'Cloze answers leaked or blanks missing');
  assert(await root.locator('#ct-answer-1104').isHidden(),'Changing questions must hide the answer');
 }
 assert(await root.locator('.ct-findings .ct-finding').count()===20,'Missing original issue dispositions');
 assert(await root.locator('.ct-original-directions .ct-finding').count()===3,'Missing original3 directions');
 assert(await root.locator('.ct-points tr').count()===result.brief.points.length,'Missing source point rows');
 if(result.visualStimuli.length){
  const s=result.visualStimuli[0];
  const task=result.document.tasks.find(t=>t.question_id===s.question_id);
  assert(Boolean(task),'Visual question not supported by a whole-direction task');
  const target=result.brief.targets.find(t=>t.directions.some(d=>d.direction_id===task.direction_id));
  await root.locator(`[data-concept="${target.concept_ids[0]}"]`).first().click();
  await root.locator('.ct-targets').getByRole('button',{name:s.question_id+' 문항 보기',exact:true}).first().click();
  const img=root.locator('.ct-stimuli img').first();await img.waitFor();
  assert(await img.evaluate(e=>e.complete&&e.naturalWidth>10),'Actual question image missing');
 }
 for(const id of [...new Set(result.visualStimuli.map(s=>s.question_id))]){
  await root.locator('.ct-question-select').selectOption(id);
  const images=root.locator('.ct-stimuli img'),expected=result.visualStimuli.filter(s=>s.question_id===id);
  assert(await images.count()===expected.length,'Missing question image '+id);
  for(let i=0;i<expected.length;i++)assert(await images.nth(i).evaluate(e=>e.complete&&e.naturalWidth>10),'Unrendered image '+id);
 }
 await page.screenshot({path:vis+'/cholinergic-corrected-question-check.png'});
 await root.locator('[data-concept]').first().click();
 await root.getByRole('link',{name:'트리로 돌아가기'}).click();
 await page.screenshot({path:vis+'/cholinergic-corrected-check.png'});
 await page.setViewportSize({width:360,height:1100});
 const child=page.frames().find(f=>f!==page.mainFrame());
 const dims=await child.evaluate(()=>({scroll:document.documentElement.scrollWidth,width:window.innerWidth}));
 assert(dims.scroll<=dims.width+1,'Narrow overflow '+JSON.stringify(dims));
 assert(!errors.length,'Browser errors '+errors.join(';'));
 const qa={pass:true,previewHash:hash(vis+'/cholinergic-corrected.html'),
  conceptSelections:result.brief.concepts.length,originalIssueDispositions:20,originalDirections:3,
  answerRevealVerified:q.question_id,narrowWidth:360,pageErrors:errors,screenshot:vis+'/cholinergic-corrected-check.png',scriptHash:hash(__filename)};
 fs.writeFileSync(base+'/preview-qa.json',JSON.stringify(qa,null,2));console.log(JSON.stringify(qa));await browser.close();
})().catch(e=>{console.error(e);process.exit(1);});
