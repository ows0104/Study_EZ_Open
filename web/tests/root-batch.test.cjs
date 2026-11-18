const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');const path=require('node:path');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const url=process.env.ROOT_BATCH_URL||'http://127.0.0.1:5195/tests/root-batch.html';
const output=process.env.ROOT_TEST_OUTPUT;
async function shot(page,name){if(output){fs.mkdirSync(output,{recursive:true});await page.screenshot({path:path.join(output,'batch-'+name+'.png'),fullPage:true});}}
async function enabled(page,name){await page.waitForFunction(name=>[...document.querySelectorAll('button')].some(b=>b.textContent.startsWith(name)&&!b.disabled),name);}
const heading=page=>page.getByRole('heading',{name:/^문항 \d+ \/ \d+$/});
/** 지금 문항의 제목 줄(강의)과 문항 글. */
async function where(page){
  await heading(page).waitFor();
  return {title:await page.locator('.mq-solve-title').innerText(),question:await page.getByText(/^(Synthetic|Second) question \d\?$/).first().innerText(),
    step:await heading(page).innerText()};
}
async function revealAndRate(page,key='3'){
  await enabled(page,'답 보기');await heading(page).focus();await page.keyboard.press('Space');
  await enabled(page,'Good');await heading(page).focus();await page.keyboard.press(key);
}

test('모아풀기: two lectures interleave, undo crosses lectures, resume and finish',async()=>{
  const browser=await chromium.launch({headless:true,channel:process.env.PLAYWRIGHT_CHANNEL||'chrome'});
  const context=await browser.newContext({viewport:{width:1360,height:900}});context.setDefaultTimeout(15000);
  await context.addInitScript(()=>localStorage.setItem('studyez:quiz-timer','off'));
  await context.route('**/api/me',r=>r.fulfill({json:{id:'a',email:'a@example.com',isApproved:true,isAdmin:false}}));
  const page=await context.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
  const events=[];
  page.on('request',r=>{if(r.method()==='POST'&&/\/sessions\/[^/]+\/events$/.test(r.url()))events.push({session:r.url().split('/').at(-2),kind:r.postDataJSON().kind});});
  try{
    // A lecture that does not exist is shown and left out; the two published ones are counted.
    await page.goto(url+'?l=test/demo&l=test/none&l=test/demo2');
    await page.getByRole('heading',{name:'모아풀기 · 3개 강의'}).waitFor();
    const list=page.getByRole('list',{name:'고른 강의'});
    await page.waitForFunction(()=>!document.querySelector('.mq-mix-list')?.textContent?.includes('…'));
    assert.match(await list.innerText(),/Synthetic root lecture[\s\S]*오늘 3문항[\s\S]*열 수 없음[\s\S]*Second root lecture[\s\S]*오늘 3문항/);
    assert.match(await page.getByRole('region',{name:'모아풀기 시작'}).innerText(),/2개 강의 · 6문항/);
    await shot(page,'start');
    await page.getByRole('button',{name:/^모아풀기 시작/}).click();

    // Equal shares → first lecture first, then alternate (largest remaining share, ties in chosen order).
    let at=await where(page);
    assert.deepEqual(at,{title:'Synthetic root lecture',question:'Synthetic question 1?',step:'문항 1 / 6'});
    await revealAndRate(page);
    at=await where(page);
    assert.deepEqual(at,{title:'Second root lecture',question:'Second question 1?',step:'문항 2 / 6'});
    await shot(page,'second-lecture');

    // Z goes back across lectures: first the rating in lecture A (answer shown again), then its reveal.
    await enabled(page,'되돌리기');await heading(page).focus();await page.keyboard.press('z');
    await page.getByText('Synthetic question 1?',{exact:true}).waitFor();await enabled(page,'Good');
    assert.equal(await heading(page).innerText(),'문항 1 / 6');
    await heading(page).focus();await page.keyboard.press('z');
    await enabled(page,'답 보기');assert.equal(await page.getByRole('button',{name:/^Good/}).count(),0);

    await revealAndRate(page);
    assert.equal((await where(page)).question,'Second question 1?');
    await revealAndRate(page);
    assert.deepEqual(await where(page),{title:'Synthetic root lecture',question:'Synthetic question 2?',step:'문항 3 / 6'});

    // Leaving and coming back resumes both open sessions where they are.
    // Every write is confirmed first (an unconfirmed one waits for 「같은 요청 다시 저장」 after a reload, as on the lecture page).
    await page.waitForFunction(()=>!Object.keys(localStorage).some(k=>k.startsWith('studyez:root-write:')));
    await page.reload();
    await page.waitForFunction(()=>(document.querySelector('.mq-mix-list')?.textContent??'').includes('남은 2문항'));
    assert.match(await list.innerText(),/Synthetic root lecture[\s\S]*남은 2문항[\s\S]*Second root lecture[\s\S]*남은 2문항/);
    await page.getByRole('button',{name:/^모아풀기 재개/}).click();
    assert.deepEqual(await where(page),{title:'Synthetic root lecture',question:'Synthetic question 2?',step:'문항 3 / 6'});

    for(const expected of ['Second question 2?','Synthetic question 3?','Second question 3?']){
      await revealAndRate(page);assert.equal((await where(page)).question,expected);
    }
    await revealAndRate(page,'4');
    await page.getByRole('heading',{name:'오늘 모아풀기를 마쳤어요'}).waitFor();
    const results=page.getByRole('list',{name:'강의별 결과'});
    await page.waitForFunction(()=>(document.querySelector('[aria-label="강의별 결과"]')?.textContent?.match(/첫 학습 2\/3/g)??[]).length===2);
    assert.match(await results.innerText(),/Synthetic root lecture[\s\S]*3문항 · 첫 학습 2\/3[\s\S]*Second root lecture[\s\S]*3문항 · 첫 학습 2\/3/);
    await shot(page,'done');

    // Z from the finished screen reopens the last question of the last lecture.
    await page.keyboard.press('z');
    assert.deepEqual(await where(page),{title:'Second root lecture',question:'Second question 3?',step:'문항 6 / 6'});
    await enabled(page,'Good');await heading(page).focus();await page.keyboard.press('3');
    await page.getByRole('heading',{name:'오늘 모아풀기를 마쳤어요'}).waitFor();

    // Each lecture got its own events: 2 sessions, and nothing was sent for the missing lecture.
    const sessions=new Set(events.map(e=>e.session));
    assert.equal(sessions.size,2);
    assert.equal(events.filter(e=>e.kind==='rate').length,8);   // 6 + A1 again after the cross-lecture undo + B3 again after the finished-screen undo
    assert.equal(events.filter(e=>e.kind==='undo').length,3);

    await page.setViewportSize({width:390,height:844});
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
    await shot(page,'done-mobile');
    assert.deepEqual(errors,[]);
  }catch(error){await shot(page,'failure');console.error((await page.locator('body').innerText()).slice(0,3000));throw error;}
  finally{await browser.close();}
});
