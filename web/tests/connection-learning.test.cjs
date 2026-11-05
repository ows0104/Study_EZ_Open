const {test} = require('node:test');
const assert = require('node:assert/strict');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const url = process.env.CONNECTION_TEST_URL || 'http://127.0.0.1:5189/tests/connection-learning.html';

test('real product screen restores drafts, reconciles lost responses and preserves conflicts', async () => {
  const browser = await chromium.launch({headless:true,channel:'chrome'});
  const context = await browser.newContext();
  const page = await context.newPage();
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  let current=0,version=0,root=null,mode='lost',posted=[];
  function view() {
    return {revision:'v1',title:'Synthetic lecture',scope:'Two synthetic bundles',count:2,version,
      state:{current,reviewSeen:false,entries:root?{b1:{root}}:{}},
      task:current===0?{id:'b1',root:root?{question:'First question?',answers:['Root answer'],explanation:'Root explanation',...root}:{question:'First question?'},
        ...(root?{follow:{question:'Follow question?'}}:{})}:{id:'b2',root:{question:'Second question?'}},map:null};
  }
  await context.route('**/api/lectures/test/demo/connections**', async route=>{
    const request=route.request(),pathname=new URL(request.url()).pathname;
    if(pathname.endsWith('/connections'))return route.fulfill({json:{canManage:false,versions:[{revision:'v1',title:'Synthetic lecture',scope:'Two synthetic bundles',count:2,published:true}]}});
    if(request.method()==='GET')return route.fulfill({json:view()});
    const p=request.postDataJSON();posted.push(p);
    if(mode==='conflict')return route.fulfill({status:409,json:{detail:'다른 탭에서 학습 기록이 바뀌었습니다.'}});
    if(mode==='lost'){
      root={response:p.response,marks:['']};version=1;mode='replay';
      return route.fulfill({status:503,json:{detail:'응답 유실'}});
    }
    // The idempotent POST response is an old snapshot; GET must win.
    return route.fulfill({json:{...view(),version:1,state:{...view().state,current:0}}});
  });
  const open=async()=>{await page.getByRole('button',{name:'Synthetic lecture · 2묶음'}).click();};
  try {
    await page.goto(url);await open();
    const response=page.getByRole('textbox',{name:'첫 질문 응답'});
    await response.fill('Unsubmitted draft');
    await page.reload();await open();assert.equal(await response.inputValue(),'Unsubmitted draft');
    await page.getByRole('button',{name:'답·설명 확인'}).click();
    await page.getByRole('button',{name:'같은 요청 다시 저장'}).waitFor();
    const original=posted[0];
    current=1;version=2;
    await page.reload();await open();
    await page.getByRole('button',{name:'같은 요청 다시 저장'}).click();
    await page.getByRole('heading',{name:'Second question?'}).waitFor();
    assert.deepEqual(posted[1],original);
    await page.waitForFunction(()=>![...Object.keys(localStorage)].some(k=>k.startsWith('studyez:connection-write:')));
    mode='conflict';
    await response.fill('Conflict draft '+ 'long '.repeat(50));
    await page.getByRole('button',{name:'답·설명 확인'}).click();
    await page.getByRole('button',{name:'서버 기록 다시 불러오기'}).click();
    await page.getByText('충돌로 반영되지 않은 응답 1개').click();
    assert.match(await page.locator('details').innerText(),/Conflict draft/);
    await page.reload();await open();
    assert.equal(await response.inputValue(),'Conflict draft '+ 'long '.repeat(50));
    await page.getByText('충돌로 반영되지 않은 응답 1개').click();
    assert.match(await page.locator('details').innerText(),/Conflict draft/);
    await page.setViewportSize({width:390,height:844});
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
    assert.deepEqual(errors,[]);
  } finally {await browser.close();}
});

test('blocked local storage keeps the live response and prevents untracked server writes', async () => {
  const browser=await chromium.launch({headless:true,channel:'chrome'});
  const page=await browser.newPage();
  let writes=0;
  await page.route('**/api/lectures/test/demo/connections**',async route=>{
    if(route.request().method()==='POST'){writes++;return route.fulfill({status:500,json:{detail:'Unexpected write'}});}
    if(route.request().url().endsWith('/connections'))return route.fulfill({json:{canManage:false,versions:[{revision:'v1',title:'Synthetic lecture',count:1,published:true}]}});
    return route.fulfill({json:{revision:'v1',title:'Synthetic lecture',scope:'One synthetic bundle',count:1,version:0,
      state:{current:0,reviewSeen:false,entries:{}},task:{id:'b1',root:{question:'First question?'}},map:null}});
  });
  try {
    await page.goto(url);await page.getByRole('button',{name:'Synthetic lecture · 1묶음'}).click();
    await page.evaluate(()=>{Storage.prototype.setItem=()=>{throw new Error('Storage blocked');};});
    const response=page.getByRole('textbox',{name:'첫 질문 응답'});
    await response.fill('Keep this input');
    await page.getByRole('alert').filter({hasText:'화면을 닫기 전에 응답을 복사하세요.'}).waitFor();
    await page.getByRole('button',{name:'답·설명 확인'}).click();
    await page.getByRole('button',{name:'같은 요청 다시 저장'}).waitFor();
    assert.equal(writes,0);assert.equal(await response.inputValue(),'Keep this input');
  } finally {await browser.close();}
});
