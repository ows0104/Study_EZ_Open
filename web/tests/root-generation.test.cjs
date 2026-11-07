const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const url=process.env.ROOT_TEST_URL;
test('actual admin UI -> queue -> live worker -> synthetic model child -> atomic publication -> study/map',async()=>{
  const browser=await chromium.launch({headless:true,channel:'chrome'});
  const context=await browser.newContext();
  await context.route('**/*',route=>{
    const u=new URL(route.request().url());
    return ['http:','https:'].includes(u.protocol)&&!['127.0.0.1','localhost'].includes(u.hostname)?route.abort():route.continue();
  });
  await context.addInitScript(()=>{
    document.addEventListener('DOMContentLoaded',()=>document.documentElement.setAttribute('data-studyez-ai-extension','1.3.23'));
    window.addEventListener('message',event=>{
      if(event.data?.source==='studyez-webapp'&&event.data.type==='STUDYEZ_OPEN_PREVIEW'){
        window.__rootDispatch=event.data.payload;
        window.postMessage({source:'studyez-ai-extension',type:'STUDYEZ_OPEN_PREVIEW_RESULT',requestId:event.data.payload.requestId,ok:true},location.origin);
      }
    });
  });
  await context.route('**/api/me',route=>route.fulfill({json:{id:'admin',email:'admin@example.com',isApproved:true,isAdmin:true}}));
  const page=await context.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
  try{
    await page.goto(url);
    await page.locator('summary').filter({hasText:/^Main Quiz 만들기$/}).first().click();
    await page.getByRole('heading',{name:'Main Quiz 만들기'}).waitFor();
    assert.equal(await page.getByRole('button',{name:'Main Quiz 만들기',exact:true}).isEnabled(),true);
    assert.equal(await page.getByLabel('Concept map 파일').count(),0);
    await page.getByText('설정·기존 지도 사용',{exact:true}).click();
    await page.getByLabel('기존 Concept map·출제포인트 사용',{exact:true}).check();
    assert.equal(await page.getByRole('button',{name:'Main Quiz 만들기',exact:true}).isDisabled(),true);
    await page.getByLabel('기존 Concept map·출제포인트 사용',{exact:true}).uncheck();
    await page.getByText('설정·기존 지도 사용',{exact:true}).click();
    const requested=page.waitForResponse(r=>r.url().endsWith('/generation')&&r.request().method()==='POST');
    await page.getByRole('button',{name:'Main Quiz 만들기',exact:true}).click();
    const queued=await requested;assert.equal(queued.status(),200);const generation=(await queued.json()).generation;
    assert.equal(generation.privatePilot,true);assert.equal(generation.input.inputMode,'source');
    assert.equal(generation.input.conceptMap,'');assert.equal(generation.input.points,'');
    assert.equal(generation.authoring,'cli');assert.equal(generation.parallelAuthoring,true);
    await page.getByRole('button',{name:'생성·업로드 진행 중',exact:true}).waitFor();
    assert.equal(await page.evaluate(()=>!!window.__rootDispatch),false);
    const worker=await fetch((process.env.GENERATION_TEST_API||'http://127.0.0.1:8028')+'/__test/process',{method:'POST'});assert.equal(worker.status,200);
    await page.getByText(/게시 완료 ·/).waitFor({timeout:45000});
    await page.getByRole('button',{name:'오늘 학습 시작',exact:true}).waitFor();
    await page.getByText('생성·검수 결과',{exact:true}).click();
    assert.match(await page.locator('main').innerText(),/목표 1개 · 준비된 과제 2개 · 수정 0\/3회/);
    await page.getByRole('button',{name:'오늘 학습 시작',exact:true}).click();
    // The actual authored question prerequisite comes first, even when it is
    // later in the original bank. A miss still opens the following connection.
    await page.getByText('Synthetic question 2?',{exact:true}).waitFor();
    assert.equal(await page.getByText('Secret answer 2',{exact:true}).count(),0);
    await page.getByRole('button',{name:/^답 확인/,exact:false}).click();
    await page.getByRole('button',{name:'1 못 떠올림',exact:true}).click();
    await page.getByText('Synthetic question 1?',{exact:true}).waitFor();
    assert.equal(await page.getByText('Secret answer 1',{exact:true}).count(),0);
    const image=page.getByRole('img',{name:'문항 그림 1',exact:true});await image.waitFor();
    assert.equal(await image.evaluate(e=>e.complete&&e.naturalWidth>0),true);
    const png=Buffer.from((await image.getAttribute('src')).split(',')[1],'base64');
    assert.equal(png.subarray(1,4).toString(),'PNG');
    const overview=await (await context.request.get(new URL('/api/root-learning/lectures/test/demo',url).href)).json();
    const livePath=new URL('/api/root-learning/sessions/'+overview.sessionId,url).href;
    const live=await (await context.request.get(livePath)).json();
    const rejected=await context.request.post(livePath+'/events',{data:{requestId:'missing-image-ack',version:live.version,kind:'reveal',attempted:true}});
    assert.equal(rejected.status(),409);
    assert.equal((await (await context.request.get(livePath)).json()).task.answer,null);
    await page.setViewportSize({width:360,height:844});
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
    if(process.env.ROOT_TEST_OUTPUT)await page.screenshot({path:path.join(process.env.ROOT_TEST_OUTPUT,'generation-visual.png'),fullPage:true});
    await page.setViewportSize({width:800,height:1000});
    // A stale/broken image view cannot record an independent visual attempt.
    const broken=await context.newPage();let brokenWrites=0;
    await broken.route('**/api/root-learning/sessions/*',async route=>{
      if(route.request().method()!=='GET')return route.continue();
      const response=await route.fetch();const data=await response.json();
      if(data.task?.question?.stimuli)data.task.question.stimuli[0].url='data:image/png;base64,invalid';
      return route.fulfill({json:data});
    });
    await broken.route('**/api/root-learning/sessions/*/events',route=>{brokenWrites++;return route.continue();});
    await broken.goto(url);await broken.getByRole('alert').filter({hasText:'문항 그림을 불러오지 못했습니다.'}).waitFor();
    assert.equal(await broken.getByRole('button',{name:/^답 확인/,exact:false}).isDisabled(),true);
    await broken.getByRole('heading',{name:'문항 2 / 2',exact:true}).focus();await broken.keyboard.press('Space');
    assert.equal(brokenWrites,0);await broken.close();
    await page.getByText('내 답 적기 · 선택',{exact:true}).click();await page.getByRole('textbox',{name:'Main Quiz 응답'}).fill('Synthetic recall');
    const revealRequest=page.waitForRequest(r=>r.url().includes('/events')&&r.postDataJSON()?.kind==='reveal');
    await page.getByRole('button',{name:/^답 확인/,exact:false}).click();
    const body=(await revealRequest).postDataJSON();
    assert.deepEqual(body.stimulusHashes,[require('node:crypto').createHash('sha256').update(png).digest('hex')]);
    await page.getByText('Secret answer 1',{exact:true}).waitFor();
    await page.getByText('출제 당시 원본 자료',{exact:true}).click();const source=page.getByRole('link',{name:'synthetic.pdf',exact:true});
    const original=await context.request.get(new URL(await source.getAttribute('href'),url).href);
    assert.equal(original.status(),200);assert.equal((await original.body()).subarray(0,4).toString(),'%PDF');
    await page.getByRole('button',{name:'지도·근거 보기 (답 포함)',exact:true}).click();
    await page.getByRole('heading',{name:'출제포인트와 실제 시험 범위'}).waitFor();
    assert.match(await page.locator('main').innerText(),/확인 2 · 일부 0 · 누락 0 · 미확인 0/);
    await page.setViewportSize({width:390,height:844});
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
    if(process.env.ROOT_TEST_OUTPUT)await page.screenshot({path:path.join(process.env.ROOT_TEST_OUTPUT,'generation-mobile.png'),fullPage:true});
    const student=await browser.newContext({extraHTTPHeaders:{'X-Root-Test-User':'student'}});
    const denied=await student.request.get(new URL('/api/root-learning/lectures/test/demo',url).href);assert.equal(denied.status(),404);
    assert.deepEqual(errors,[]);
  }finally{await browser.close();}
});
