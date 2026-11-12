// 단답·나열 「선지 보기」(docs/changes/2026-11-12-recall-choices). API: server/tests/serve_main_quiz_recall_fixture.py
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');const path=require('node:path');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const url=process.env.ROOT_TEST_URL||'http://127.0.0.1:5193/tests/root-learning.html';
async function open(browser,userId){
  const context=await browser.newContext({extraHTTPHeaders:{'X-Root-Test-User':userId}});context.setDefaultTimeout(15000);
  await context.addInitScript(()=>localStorage.setItem('studyez:quiz-timer','off'));
  await context.route('**/api/me',r=>r.fulfill({json:{id:userId,email:userId+'@example.com',isApproved:true,isAdmin:false}}));
  const page=await context.newPage(),errors=[],reveals=[];page.on('pageerror',e=>errors.push(e.message));
  page.on('request',r=>{if(r.method()==='POST'&&r.url().endsWith('/events')){const b=r.postDataJSON();if(b.kind==='reveal')reveals.push(b);}});
  await page.goto(url);await page.getByRole('button',{name:'오늘 학습 시작',exact:true}).click();
  return {context,page,errors,reveals};
}
async function enabled(page,name){await page.waitForFunction(name=>[...document.querySelectorAll('button')].some(b=>b.textContent.startsWith(name)&&!b.disabled),name);}
async function shot(page,name){if(process.env.ROOT_TEST_OUTPUT){fs.mkdirSync(process.env.ROOT_TEST_OUTPUT,{recursive:true});await page.screenshot({path:path.join(process.env.ROOT_TEST_OUTPUT,name+'.png'),fullPage:true});}}
const options=page=>page.locator('.bank-option');
// 답은 저장 왕복을 기다리지 않고 열린다. 요청이 실제로 나갈 때까지 기다려 그 본문을 본다.
async function reveal(reveals,n){for(let i=0;i<150&&reveals.length<n;i++)await new Promise(r=>setTimeout(r,100));assert.equal(reveals.length,n);return reveals[n-1];}
const opener=page=>page.getByRole('button',{name:/^선지 보기/});

test('V opens hidden choices, Space still reveals, results are marked, opened attempts are reported',async()=>{
  const browser=await chromium.launch({headless:true,channel:'chrome'});
  try{
    const {page,errors,reveals}=await open(browser,'recall-open-'+Date.now());
    // 단답: 처음엔 선지가 없고 버튼만 있다. V로 편다.
    await page.getByText('Which vector carries epidemic typhus?',{exact:true}).waitFor();await enabled(page,'답 보기');
    assert.equal(await options(page).count(),0);await opener(page).waitFor();await shot(page,'recall-1-closed');
    await page.getByRole('heading',{name:'문항 1 / 3'}).focus();await page.keyboard.press('v');
    await options(page).first().waitFor();assert.equal(await options(page).count(),4);assert.equal(await opener(page).count(),0);
    await page.getByText('하나를 고르세요.',{exact:true}).waitFor();
    // 단답은 하나만 고른다.
    await page.getByRole('button',{name:/Body louse/}).click();await page.getByRole('button',{name:/Rat flea/}).click();
    assert.equal(await page.locator('.bank-option.is-picked').count(),1);await shot(page,'recall-2-open');
    // 새로고침해도 편 상태와 고른 선지가 남는다.
    await page.reload();await options(page).first().waitFor();assert.equal(await page.locator('.bank-option.is-picked').count(),1);
    await page.getByRole('heading',{name:'문항 1 / 3'}).focus();await page.keyboard.press('Space');await enabled(page,'Good');
    assert.equal((await reveal(reveals,1)).choicesShown,true);
    assert.match(await page.locator('.bank-option.is-missed').innerText(),/Body louse/);
    assert.match(await page.locator('.bank-option.is-wrong').innerText(),/Rat flea/);await shot(page,'recall-3-answer');
    await page.keyboard.press('3');
    // 나열: 여러 개를 고른다.
    await page.getByText('List the host factors.',{exact:true}).waitFor();await enabled(page,'답 보기');
    assert.equal(await options(page).count(),0);await opener(page).click();assert.equal(await options(page).count(),5);
    await page.getByText('해당하는 것을 모두 고르세요.',{exact:true}).waitFor();
    for(const name of ['Age','Nutrition','Occupation'])await page.getByRole('button',{name:new RegExp(name)}).click();
    assert.equal(await page.locator('.bank-option.is-picked').count(),3);
    await page.getByRole('heading',{name:'문항 2 / 3'}).focus();await page.keyboard.press('Space');await enabled(page,'Good');
    assert.equal(await page.locator('.bank-option.is-correct').count(),2);
    assert.equal(await page.locator('.bank-option.is-missed').count(),1);
    assert.equal(await page.locator('.bank-option.is-wrong').count(),1);await shot(page,'recall-4-list');
    assert.equal(await page.getByText('해당하는 것을 모두 고르세요.',{exact:true}).count(),0);
    await page.keyboard.press('3');
    // 선지가 없는 문항은 지금과 같다. V는 아무 일도 하지 않는다.
    await page.getByText('Synthetic question 3?',{exact:true}).waitFor();await enabled(page,'답 보기');
    assert.equal(await opener(page).count(),0);await page.getByRole('heading',{name:'문항 3 / 3'}).focus();await page.keyboard.press('v');
    assert.equal(await options(page).count(),0);
    await page.keyboard.press('Space');await enabled(page,'Good');assert.equal((await reveal(reveals,3)).choicesShown,false);
    assert.equal(reveals[1].choicesShown,true);assert.deepEqual(errors,[]);
  }finally{await browser.close();}
});

test('Space without opening reveals the answer and reports a plain attempt',async()=>{
  const browser=await chromium.launch({headless:true,channel:'chrome'});
  try{
    const {page,errors,reveals}=await open(browser,'recall-closed-'+Date.now());
    await page.getByText('Which vector carries epidemic typhus?',{exact:true}).waitFor();await enabled(page,'답 보기');await opener(page).waitFor();
    await page.getByRole('heading',{name:'문항 1 / 3'}).focus();await page.keyboard.press('Space');await enabled(page,'Good');
    assert.equal((await reveal(reveals,1)).choicesShown,false);assert.equal(await options(page).count(),0);assert.equal(await opener(page).count(),0);
    // Ctrl+V는 선지를 펴지 않는다.
    await page.keyboard.press('3');await page.getByText('List the host factors.',{exact:true}).waitFor();await enabled(page,'답 보기');
    await page.getByRole('heading',{name:'문항 2 / 3'}).focus();await page.keyboard.press('Control+v');
    assert.equal(await options(page).count(),0);await opener(page).waitFor();
    assert.deepEqual(errors,[]);
  }finally{await browser.close();}
});
