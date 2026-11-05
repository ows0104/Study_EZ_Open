const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const url=process.env.ROOT_TEST_URL||'http://127.0.0.1:5193/tests/root-learning.html';

test('real product and isolated API: drafts, lost reply, two tabs, goals, undo, help and finite completion',async()=>{
  const browser=await chromium.launch({headless:true,channel:'chrome'});
  const context=await browser.newContext();
  await context.route('**/api/me',route=>route.fulfill({json:{id:'a',email:'a@example.com',isApproved:true,isAdmin:false}}));
  const page=await context.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
  let lose=true;const attempts=[];
  await page.route('**/api/root-learning/sessions/*/events',async route=>{
    const body=route.request().postDataJSON();
    if(body.kind==='reveal')attempts.push(body);
    if(lose&&body.kind==='reveal'){
      lose=false;const response=await route.fetch();assert.equal(response.status(),200);
      return route.fulfill({status:503,json:{detail:'저장 응답 유실'}});
    }
    return route.continue();
  });
  try {
    await page.goto(url);await page.getByText(/한국시간 04:00에 새 학습일/).waitFor();
    await page.getByRole('button',{name:'오늘 학습 시작',exact:true}).click();
    const response=page.getByRole('textbox',{name:'뿌리 질문 응답'});
    await page.waitForFunction(()=>[...document.querySelectorAll('button')].some(b=>b.textContent==='떠올려본 뒤 답 확인'&&!b.disabled));
    await response.fill('Keep my first attempt');
    await page.reload();await response.waitFor();assert.equal(await response.inputValue(),'Keep my first attempt');
    const other=await context.newPage();await other.goto(url);await other.getByRole('textbox',{name:'뿌리 질문 응답'}).fill('Other tab draft');
    await page.getByRole('button',{name:'떠올려본 뒤 답 확인',exact:true}).click();
    await page.getByRole('button',{name:'같은 요청 다시 저장'}).waitFor();
    await other.getByRole('button',{name:'떠올려본 뒤 답 확인',exact:true}).click();
    await other.getByRole('button',{name:'보관 응답 확인 후 서버 기록 불러오기'}).waitFor();
    await page.reload();await page.getByRole('button',{name:'같은 요청 다시 저장'}).click();
    await page.getByRole('button',{name:'보관 응답 확인 후 서버 기록 불러오기'}).click();
    assert.deepEqual(attempts[1],attempts[0]);
    await page.getByText('보존된 충돌 응답 1개').click();assert.match(await page.locator('details').first().innerText(),/Other tab draft/);
    await other.close();
    assert.equal(await response.inputValue(),'Keep my first attempt');
    await page.getByRole('button',{name:'2 일부만·도움 받아 떠올림',exact:true}).click();
    await page.getByText('Synthetic question 2?',{exact:true}).waitFor();
    await page.getByRole('button',{name:'직전 자기평가 취소',exact:true}).click();
    await page.getByText('Synthetic question 1?',{exact:true}).waitFor();
    await page.getByRole('button',{name:'3 스스로 떠올림',exact:true}).click();
    await page.getByText('Synthetic question 2?',{exact:true}).waitFor();
    await page.getByRole('button',{name:'답만 보기',exact:true}).click();
    assert.equal(await page.getByRole('button',{name:'3 스스로 떠올림',exact:true}).isDisabled(),true);
    await page.getByRole('button',{name:'지도·근거 보기 (답 포함)',exact:true}).click();
    await page.getByRole('heading',{name:'뿌리 지도와 근거'}).waitFor();
    await page.getByRole('button',{name:'현재 질문',exact:true}).click();
    await page.getByText('Synthetic question 2?',{exact:true}).waitFor();
    await page.getByRole('button',{name:'2 일부만·도움 받아 떠올림',exact:true}).click();
    await page.getByText('Synthetic question 3?',{exact:true}).waitFor();
    await page.getByRole('heading',{name:'현재 연결 3',exact:true}).focus();
    await page.keyboard.press('Space');
    await page.getByRole('button',{name:'2 일부만·도움 받아 떠올림',exact:true}).waitFor();
    await page.waitForFunction(()=>[...document.querySelectorAll('button')].some(b=>b.textContent==='2 일부만·도움 받아 떠올림'&&!b.disabled));
    await page.keyboard.press('2');
    await page.getByRole('heading',{name:'오늘 목록 종료',exact:true}).waitFor();
    assert.match(await page.getByRole('region',{name:'뿌리 학습 현황'}).innerText(),/고유 목표 3개 · 첫 학습 2/);
    assert.match(await page.locator('main').innerText(),/준비 전 1/);
    await page.setViewportSize({width:390,height:844});
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
    if(process.env.ROOT_TEST_OUTPUT){fs.mkdirSync(process.env.ROOT_TEST_OUTPUT,{recursive:true});await page.screenshot({path:path.join(process.env.ROOT_TEST_OUTPUT,'mobile.png'),fullPage:true});}
    assert.deepEqual(errors,[]);
  }finally{await browser.close();}
});

test('blocked storage prevents untracked writes and malformed pending requests remain preserved',async()=>{
  const browser=await chromium.launch({headless:true,channel:'chrome'});
  let posts=0;
  const context=await browser.newContext({extraHTTPHeaders:{'X-Root-Test-User':'storage-user'}});
  await context.route('**/api/me',route=>route.fulfill({json:{id:'storage-user',isApproved:true,isAdmin:false}}));
  await context.route('**/api/root-learning/lectures/test/demo/sessions',route=>{
    if(route.request().method()==='POST')posts++;
    return route.continue();
  });
  const page=await context.newPage();
  try{
    await page.goto(url);
    await page.getByRole('button',{name:'오늘 학습 시작',exact:true}).waitFor();
    await page.evaluate(()=>{Storage.prototype.setItem=()=>{throw new Error('Storage blocked');};});
    await page.getByRole('button',{name:'오늘 학습 시작',exact:true}).click();
    await page.getByRole('alert').filter({hasText:'이 브라우저에 보관하지 못했습니다.'}).waitFor();
    assert.equal(posts,0);
    await page.getByRole('button',{name:'같은 요청 다시 저장'}).waitFor();
    await context.close();
    const corrupt=await browser.newContext({extraHTTPHeaders:{'X-Root-Test-User':'corrupt-user'}});
    const key='studyez:root-write:["","test","demo"]:broken';
    await corrupt.addInitScript(key=>localStorage.setItem(key,'{broken'),key);
    const broken=await corrupt.newPage();await broken.goto(url);
    await broken.getByRole('alert').filter({hasText:'원본을 보존했으며 새 저장은 중지했습니다.'}).waitFor();
    assert.equal(await broken.getByRole('button',{name:'오늘 학습 시작',exact:true}).isDisabled(),true);
    assert.equal(await broken.evaluate(key=>localStorage.getItem(key),key),'{broken');
    await corrupt.close();
  }finally{await browser.close();}
});
