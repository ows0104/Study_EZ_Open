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
/** 시작 화면의 수가 다 읽힐 때까지. */
async function counted(page){await page.waitForFunction(()=>{const t=document.querySelector('.mq-mix-list')?.textContent;return t&&!t.includes('…');});}
const lectureRows=page=>page.getByRole('list',{name:'고른 강의'}).locator('li');
const startCount=page=>page.locator('.mq-start-button .mq-card-count').innerText();
const globalChip=(page,tier)=>page.getByRole('group',{name:'중요도',exact:true}).getByRole('button').filter({hasText:tier});

async function launch(user){
  const browser=await chromium.launch({headless:true,channel:process.env.PLAYWRIGHT_CHANNEL||'chrome'});
  const context=await browser.newContext({viewport:{width:1360,height:900},extraHTTPHeaders:{'X-Root-Test-User':user}});
  context.setDefaultTimeout(15000);
  await context.addInitScript(()=>localStorage.setItem('studyez:quiz-timer','off'));
  await context.route('**/api/me',r=>r.fulfill({json:{id:user,email:user+'@example.com',isApproved:true,isAdmin:false}}));
  return {browser,page:await context.newPage()};
}

test('모아풀기 시작 화면: 선택지·강의별 중요도·순서대로·강의를 건넌 Z·재개·마침',async()=>{
  const {browser,page}=await launch('a');const errors=[];page.on('pageerror',e=>errors.push(e.message));
  const events=[];
  page.on('request',r=>{if(r.method()==='POST'&&/\/sessions\/[^/]+\/events$/.test(r.url()))events.push({session:r.url().split('/').at(-2),kind:r.postDataJSON().kind});});
  try{
    // A lecture that does not exist is shown and left out.
    await page.goto(url+'?l=test/demo&l=test/none&l=test/demo2');
    await page.getByRole('heading',{name:'모아풀기 · 3개 강의'}).waitFor();
    await counted(page);
    // 모아풀기 화면에는 강의 하나로 가는 길을 두지 않는다(2026-11-18 사용자 「없애줘」).
    assert.equal(await page.getByText('이 강의만').count(),0);
    // Nothing studied yet: without 미열람 문항 보기 there is nothing to solve.
    assert.match(await page.getByRole('list',{name:'고른 강의'}).innerText(),/Synthetic root lecture[\s\S]*0문항[\s\S]*열 수 없음[\s\S]*Second root lecture[\s\S]*0문항/);
    assert.equal(await startCount(page),'0');
    assert.equal(await page.getByRole('button',{name:/^모아풀기 시작/}).isDisabled(),true);

    await page.getByLabel('미열람 문항 보기').check();
    assert.equal(await startCount(page),'6');
    assert.match(await globalChip(page,'Core').innerText(),/Core\s*6/);
    assert.equal(await globalChip(page,'Core').getAttribute('aria-pressed'),'true');

    // 강의별: 처음부터 펼쳐 있다(2026-11-27-mix-lane-focus). 한 강의의 Core를 끄면 그 강의만 0, 전체 칩은 「일부」.
    assert.equal(await page.getByRole('button',{name:'강의별'}).getAttribute('aria-expanded'),'true');
    const second=lectureRows(page).filter({hasText:'Second root lecture'});
    await second.getByRole('button').filter({hasText:'Core'}).click();
    assert.match(await second.innerText(),/0문항/);
    assert.equal(await startCount(page),'3');
    assert.equal(await globalChip(page,'Core').getAttribute('aria-pressed'),'mixed');
    await shot(page,'start-per-lecture');
    // 전체 칩을 누르면 모든 강의에 다시 적용된다.
    await globalChip(page,'Core').click();
    assert.equal(await globalChip(page,'Core').getAttribute('aria-pressed'),'true');
    assert.equal(await startCount(page),'6');
    // 마지막 남은 전체 칩은 끌 수 없다(다른 중요도는 0개라도 켜져 있어 Core는 끌 수 있다).
    for(const tier of ['Essential','Important','Optional'])await globalChip(page,tier).click();
    assert.equal(await globalChip(page,'Core').isDisabled(),true);
    assert.equal(await startCount(page),'6');

    await page.getByRole('button',{name:/^모아풀기 시작/}).click();
    // 순서대로: 강의 번호 순으로 한 강의를 끝낸 뒤 다음 강의.
    for(const [i,question] of ['Synthetic question 1?','Synthetic question 2?','Synthetic question 3?'].entries()){
      assert.deepEqual(await where(page),{title:'Synthetic root lecture',question,step:`문항 ${i+1} / 6`});
      await revealAndRate(page);
    }
    assert.deepEqual(await where(page),{title:'Second root lecture',question:'Second question 1?',step:'문항 4 / 6'});

    // 강의명 숨기기(2026-11-24): 우상단 스위치로 머리줄 강의명만 감춘다.
    const hide=page.getByRole('switch',{name:'강의명 숨기기'});
    assert.equal(await hide.getAttribute('aria-checked'),'false');
    await hide.click();
    assert.equal(await hide.getAttribute('aria-checked'),'true');
    assert.equal(await page.locator('.mq-solve-title').count(),0);
    await page.getByText('Second question 1?',{exact:true}).waitFor();
    await shot(page,'hide-lecture');
    await hide.click();
    assert.equal(await page.locator('.mq-solve-title').innerText(),'Second root lecture');

    // Z goes back across lectures: first the rating in lecture A (answer shown again), then its reveal.
    await enabled(page,'되돌리기');await heading(page).focus();await page.keyboard.press('z');
    await page.getByText('Synthetic question 3?',{exact:true}).waitFor();await enabled(page,'Good');
    assert.equal(await heading(page).innerText(),'문항 3 / 6');
    await heading(page).focus();await page.keyboard.press('z');
    await enabled(page,'답 보기');assert.equal(await page.getByRole('button',{name:/^Good/}).count(),0);
    await revealAndRate(page);
    await revealAndRate(page);
    assert.deepEqual(await where(page),{title:'Second root lecture',question:'Second question 2?',step:'문항 5 / 6'});

    // Leaving and coming back: the same options resume the open sessions.
    await page.waitForFunction(()=>!Object.keys(localStorage).some(k=>k.startsWith('studyez:root-write:')));
    await page.reload();
    await counted(page);
    // Default options again: the four solved today are not due, the two left are unseen.
    assert.equal(await startCount(page),'0');
    await page.getByLabel('미열람 문항 보기').check();
    // 다른 조건(중요도 넷)이면 새 회차 자리다. 시작할 때와 같은 조건(Core만)이면 그 회차를 잇는다.
    assert.equal(await page.getByRole('button',{name:/^모아풀기 시작/}).count(),1);
    for(const tier of ['Essential','Important','Optional'])await globalChip(page,tier).click();
    await page.waitForFunction(()=>(document.querySelector('.mq-mix-list')?.textContent??'').includes('남은 2문항'));
    assert.match(await page.getByRole('list',{name:'고른 강의'}).innerText(),/Synthetic root lecture[\s\S]*0문항[\s\S]*Second root lecture[\s\S]*남은 2문항/);
    await page.getByRole('button',{name:/^모아풀기 재개/}).click();
    assert.deepEqual(await where(page),{title:'Second root lecture',question:'Second question 2?',step:'문항 2 / 3'});
    await revealAndRate(page);
    assert.equal((await where(page)).question,'Second question 3?');
    await revealAndRate(page,'4');
    await page.getByRole('heading',{name:'오늘 모아풀기를 마쳤어요'}).waitFor();
    // Lecture A was finished before the reload: it still shows among the results (#219 e198b5c8).
    await page.waitForFunction(()=>(document.querySelector('[aria-label="강의별 결과"]')?.textContent?.match(/첫 학습 2\/3/g)??[]).length===2);
    assert.match(await page.getByRole('list',{name:'강의별 결과'}).innerText(),/Synthetic root lecture[\s\S]*3문항 · 첫 학습 2\/3[\s\S]*Second root lecture[\s\S]*3문항 · 첫 학습 2\/3/);
    assert.match(await page.locator('.mq-done-card').innerText(),/2개 강의 · 6문항/);
    await shot(page,'done');

    // 복습 주기 이전 문제도 보기(예전 이름 「기존 학습률 무시」): today's six are counted again; 미열람은 없다.
    await page.getByRole('button',{name:'강의 목록으로'}).waitFor();
    await page.goto(url+'?l=test/demo&l=test/demo2');
    await counted(page);
    assert.equal(await startCount(page),'0');
    await page.getByLabel('미열람 문항 보기').check();
    assert.equal(await startCount(page),'0');
    await page.getByLabel('복습 주기 이전 문제도 보기').check();
    assert.equal(await startCount(page),'6');

    const sessions=new Set(events.map(e=>e.session));
    assert.equal(sessions.size,2);
    assert.equal(events.filter(e=>e.kind==='rate').length,7);   // 6 + A3 again after the cross-lecture undo
    assert.equal(events.filter(e=>e.kind==='undo').length,2);

    await page.setViewportSize({width:390,height:844});
    assert.equal(await page.getByRole('button',{name:'강의별'}).getAttribute('aria-expanded'),'true');
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
    await shot(page,'start-mobile');
    assert.deepEqual(errors,[]);
  }catch(error){await shot(page,'failure');console.error((await page.locator('body').innerText()).slice(0,3000));throw error;}
  finally{await browser.close();}
});

test('모아풀기 섞어서: 강의 사이·강의 안을 모두 섞고 모든 문항을 한 번씩 낸다',async()=>{
  const {browser,page}=await launch('b');const errors=[];page.on('pageerror',e=>errors.push(e.message));
  try{
    await page.goto(url+'?l=test/demo&l=test/demo2');
    await counted(page);
    await page.getByLabel('미열람 문항 보기').check();
    await page.getByRole('radio',{name:'섞어서'}).click();
    await page.getByRole('button',{name:/^모아풀기 시작/}).click();
    const seen=[];
    for(let i=1;i<=6;i++){
      const at=await where(page);
      assert.equal(at.step,`문항 ${i} / 6`);
      seen.push(at.question);
      await revealAndRate(page);
    }
    await page.getByRole('heading',{name:'오늘 모아풀기를 마쳤어요'}).waitFor();
    assert.deepEqual([...seen].sort(),['Second question 1?','Second question 2?','Second question 3?',
      'Synthetic question 1?','Synthetic question 2?','Synthetic question 3?']);
    console.log('섞어서 순서:',seen.join(' → '));
    assert.deepEqual(errors,[]);
  }catch(error){await shot(page,'failure-random');console.error((await page.locator('body').innerText()).slice(0,3000));throw error;}
  finally{await browser.close();}
});

test('모아풀기 묶음: 강의를 건너 미열람을 먼저, 복습 주기 이전 문항은 그 뒤(2026-11-19-mix-urgency-order)',async()=>{
  const {browser,page}=await launch('c');const errors=[];page.on('pageerror',e=>errors.push(e.message));
  try{
    await page.goto(url+'?l=test/demo&l=test/demo2');
    await counted(page);
    await page.getByLabel('미열람 문항 보기').check();
    await page.getByRole('button',{name:/^모아풀기 시작/}).click();
    // 순서대로: lecture A first. Solve two, then leave.
    assert.equal((await where(page)).question,'Synthetic question 1?');await revealAndRate(page);
    assert.equal((await where(page)).question,'Synthetic question 2?');await revealAndRate(page);
    await where(page);
    await page.waitForFunction(()=>!Object.keys(localStorage).some(k=>k.startsWith('studyez:root-write:')));
    await page.reload();
    await counted(page);
    // A1·A2 are now not yet due; A3 and B1–B3 are unseen. Other options → a new mixed session.
    await page.getByLabel('미열람 문항 보기').check();
    await page.getByLabel('복습 주기 이전 문제도 보기').check();
    await page.getByRole('radio',{name:'섞어서'}).click();
    assert.equal(await startCount(page),'6');
    await page.getByRole('button',{name:/^모아풀기 시작/}).click();
    const seen=[];
    for(let i=0;i<6;i++){seen.push((await where(page)).question);await revealAndRate(page);}
    await page.getByRole('heading',{name:'오늘 모아풀기를 마쳤어요'}).waitFor();
    console.log('묶음 순서:',seen.join(' → '));
    assert.deepEqual(seen.slice(0,4).sort(),['Second question 1?','Second question 2?','Second question 3?','Synthetic question 3?']);
    assert.deepEqual(seen.slice(4).sort(),['Synthetic question 1?','Synthetic question 2?']);
    assert.deepEqual(errors,[]);
  }catch(error){await shot(page,'failure-phases');console.error((await page.locator('body').innerText()).slice(0,3000));throw error;}
  finally{await browser.close();}
});

test('모아풀기 강의별 중요도: 강의 화면에 저장한 중요도가 기본값, 고른 적 없는 강의는 전부(2026-11-27-mix-lane-focus)',async()=>{
  const {browser,page}=await launch('d');const errors=[];page.on('pageerror',e=>errors.push(e.message));
  try{
    // 두 번째 강의만 강의 화면에서 Essential만 골라 두었다(PUT …/focus, 오늘 학습 칩과 같은 저장).
    const api=new URL('/api/root-learning/lectures/test/demo2/focus',url).href;
    const saved=await page.request.put(api,{data:{requestId:'d-focus-1',tiers:['Essential']}});
    assert.equal(saved.status(),200,await saved.text());
    await page.goto(url+'?l=test/demo&l=test/demo2');
    await counted(page);
    await page.getByLabel('미열람 문항 보기').check();
    const first=lectureRows(page).filter({hasText:'Synthetic root lecture'}),second=lectureRows(page).filter({hasText:'Second root lecture'});
    const pressed=async row=>(await Promise.all((await row.getByRole('button').all()).map(async b=>(await b.getAttribute('aria-pressed'))==='true'?(await b.innerText()).replace(/\s*\d+$/,''):null))).filter(Boolean);
    assert.deepEqual(await pressed(first),['Essential','Core','Important','Optional']);
    assert.deepEqual(await pressed(second),['Essential']);
    assert.match(await second.innerText(),/0문항/);
    assert.equal(await startCount(page),'3');
    assert.equal(await globalChip(page,'Core').getAttribute('aria-pressed'),'mixed');
    assert.equal(await globalChip(page,'Essential').getAttribute('aria-pressed'),'true');
    await shot(page,'start-saved-focus');
    // 여기서 바꾸면 그 강의만 바뀌고, 강의 화면의 저장값은 그대로다.
    await second.getByRole('button').filter({hasText:'Core'}).click();
    assert.equal(await startCount(page),'6');
    const after=await page.request.get(new URL('/api/root-learning/lectures/test/demo2/mix',url).href);
    assert.deepEqual((await after.json()).focus,['Essential']);
    assert.deepEqual(errors,[]);
  }catch(error){await shot(page,'failure-saved-focus');console.error((await page.locator('body').innerText()).slice(0,3000));throw error;}
  finally{await browser.close();}
});
