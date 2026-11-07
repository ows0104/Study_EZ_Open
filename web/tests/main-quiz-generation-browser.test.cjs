const {test}=require('node:test');const assert=require('node:assert/strict');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
test('actual React button queues CLI work without a bridge and observes publication',async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});const page=await browser.newPage();const writes=[];const errors=[];let generation=null;
 page.on('pageerror',e=>errors.push(e.message));
 await page.route('**/api/**',async route=>{
  const req=route.request();if(req.method()==='POST'){
   writes.push(req.postDataJSON());generation={id:'synthetic',state:'queued',stage:'CLI 병렬 대기',published:false,input:{inputMode:'source',conceptMap:'',points:'',scope:'',examDate:null},privatePilot:true,authoring:'cli',parallelAuthoring:true,featureEnabled:true};
  }
  await route.fulfill({json:{generation}});
 });
 try{
  await page.goto(process.env.GENERATION_BUTTON_URL);
  const button=page.getByRole('button',{name:'Main Quiz 만들기',exact:true});await button.waitFor();await button.click();
  await page.getByRole('button',{name:'생성·업로드 진행 중',exact:true}).waitFor();
  assert.equal(writes.length,1);assert.equal(writes[0].authoring,'cli');assert.equal(writes[0].parallelAuthoring,true);assert.equal(writes[0].inputMode,'source');
  assert.equal(await page.getByRole('button').count(),1);assert.equal(await page.getByText('문제은행 링크',{exact:true}).count(),0);
  generation={...generation,state:'running',stage:'원본·정답 검수'};
  await page.getByRole('status').filter({hasText:'원본·정답 검수'}).waitFor({timeout:10000});
  await page.setViewportSize({width:390,height:844});
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
  if(process.env.GENERATION_BUTTON_SCREENSHOT)await page.screenshot({path:process.env.GENERATION_BUTTON_SCREENSHOT,fullPage:true});
  generation={...generation,state:'done',stage:'',published:true};
  await page.getByRole('link',{name:'Main Quiz 열기 →',exact:true}).waitFor({timeout:10000});
  assert.equal(await page.getByLabel('자료 갱신 횟수').innerText(),'1');assert.deepEqual(errors,[]);
 }finally{await browser.close();}
});
