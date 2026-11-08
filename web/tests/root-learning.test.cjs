const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');const path=require('node:path');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const url=process.env.ROOT_TEST_URL||'http://127.0.0.1:5193/tests/root-learning.html';
const ratings=['Again','Hard','Good','Easy'];
async function contextFor(browser,options){const context=await browser.newContext(options);context.setDefaultTimeout(15000);return context;}
async function enabled(page,name){await page.getByRole('button',{name,exact:false}).waitFor();await page.waitForFunction(name=>[...document.querySelectorAll('button')].some(b=>b.textContent.startsWith(name)&&!b.disabled),name);}
async function allRatings(page){for(const r of ratings){await enabled(page,r);assert.equal(await page.getByRole('button',{name:new RegExp('^'+r)}).isEnabled(),true);}}
async function screenshot(page,name){if(process.env.ROOT_TEST_OUTPUT){fs.mkdirSync(process.env.ROOT_TEST_OUTPUT,{recursive:true});await page.screenshot({path:path.join(process.env.ROOT_TEST_OUTPUT,name+'.png'),fullPage:true});}}

test('actual API: no textbox, preserved drafts/retries/conflicts, four ratings, PDF page, graph and undo',async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});const context=await contextFor(browser);
 await context.route('**/api/me',r=>r.fulfill({json:{id:'a',email:'a@example.com',isApproved:true,isAdmin:false}}));
 const page=await context.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
 const draft='studyez:root-draft:["","test","demo"]:["v1","task1"]';
 await page.addInitScript(key=>{if(localStorage.getItem(key)===null)localStorage.setItem(key,'retired draft preserved');},draft);
 let lose=true;const attempts=[];
 await context.route('**/api/root-learning/sessions/*/events',async route=>{
   const body=route.request().postDataJSON();if(body.kind==='reveal')attempts.push(body);
   if(lose&&body.kind==='reveal'){lose=false;const result=await route.fetch();assert.equal(result.status(),200);return route.fulfill({status:503,json:{detail:'저장 응답 유실'}});}
   return route.continue();
 });
 try{
   await page.goto(url);await page.getByText('학습 현황·자료 범위',{exact:true}).click();await page.getByText(/한국시간 04:00/).waitFor();
   await page.getByRole('button',{name:'오늘 학습 시작',exact:true}).click();await enabled(page,'답 보기');
   assert.equal(await page.locator('textarea').count(),0);await page.addInitScript(()=>{window.__sawStart=false;new MutationObserver(()=>{if(document.querySelector('.mq-start-button'))window.__sawStart=true;}).observe(document,{subtree:true,childList:true});});await page.reload();await enabled(page,'답 보기');assert.equal(await page.evaluate(()=>window.__sawStart),false,'resuming an open session never draws the start screen first');
   assert.equal(await page.evaluate(key=>localStorage.getItem(key),draft),'retired draft preserved');
   const other=await context.newPage();await other.goto(url);await enabled(other,'답 보기');
   await page.getByRole('heading',{name:'문항 1 / 3'}).focus();await page.keyboard.press('Space');
   await page.getByRole('button',{name:'같은 요청 다시 저장'}).waitFor();
   await other.getByRole('button',{name:/^답 보기/}).click();await other.getByRole('button',{name:'보관 응답 확인 후 서버 기록 불러오기'}).waitFor();
   await other.close();await page.reload();await page.getByRole('button',{name:'같은 요청 다시 저장'}).click();
   await page.getByRole('button',{name:'보관 응답 확인 후 서버 기록 불러오기'}).click();
   assert.deepEqual(attempts[2],attempts[0]);await allRatings(page);
   assert.equal(await page.evaluate(key=>localStorage.getItem(key),draft),'retired draft preserved');
   const slide=page.getByRole('img',{name:'two-pages.pdf · PDF 2쪽',exact:true});await slide.waitFor();
   assert.equal(await slide.evaluate(img=>img.complete&&img.naturalWidth>300),true);
   await screenshot(page,'restored-answer-desktop');
   await page.getByRole('button',{name:/^Hard/}).click();await page.getByText('Synthetic question 2?',{exact:true}).waitFor();
   await enabled(page,'되돌리기');await page.getByRole('heading',{name:'문항 2 / 3'}).focus();await page.keyboard.press('z');
   await page.getByText('Synthetic question 1?',{exact:true}).waitFor();await allRatings(page);await page.keyboard.press('3');
   await page.getByText('Synthetic question 2?',{exact:true}).waitFor();await page.getByText('더 보기',{exact:true}).click();
   await page.getByRole('button',{name:'답만 보기',exact:true}).click();await allRatings(page);
   await page.getByRole('button',{name:'개념 지도',exact:true}).click();await page.getByRole('heading',{name:'개념 지도',exact:true}).waitFor();
   // Lane view: every topic is on screen at a readable scale before any click; questions are status dots.
   const graph=page.getByRole('group',{name:'개념 트리'});assert.equal(await graph.locator('.mq-lane-node').count(),3);
   assert.equal(await graph.locator('.mq-lane-dots i').count(),3);
   assert.equal(await page.locator('.main-quiz-tree-stage').evaluate(stage=>{const s=stage.getBoundingClientRect();
     return [...stage.querySelectorAll('[data-node]')].every(n=>{const r=n.getBoundingClientRect();return r.left>=s.left&&r.right<=s.right&&r.top>=s.top&&r.bottom<=s.bottom;});}),true);
   assert.ok(await graph.evaluate(w=>new DOMMatrix(getComputedStyle(w).transform).a)>=0.6);
   await graph.getByRole('button',{name:/^주제 A ·/}).click();await page.getByRole('heading',{name:'A',exact:true}).waitFor();
   assert.equal(await graph.getByRole('button',{name:/^주제 A ·/}).getAttribute('aria-expanded'),'true');
   await graph.getByRole('button',{name:/^주제 C ·/}).click();await graph.getByRole('button',{name:/^주제 C ·/}).click();
   assert.equal(await graph.getByRole('button',{name:/^주제 C ·/}).getAttribute('aria-expanded'),'false');
   await page.getByRole('button',{name:'문항 펼치기',exact:true}).click();assert.equal(await graph.locator('.mq-lane-q').count(),3);
   await screenshot(page,'concept-map-desktop');await page.setViewportSize({width:390,height:844});
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);await screenshot(page,'concept-map-mobile');
   await page.getByRole('button',{name:'← 문제로 돌아가기',exact:true}).click();await allRatings(page);
   await screenshot(page,'restored-answer-mobile');await page.getByRole('heading',{name:'문항 2 / 3'}).focus();await page.keyboard.press('4');
   await page.getByText('Synthetic question 3?',{exact:true}).waitFor();await enabled(page,'답 보기');await page.getByRole('heading',{name:'문항 3 / 3'}).focus();await page.keyboard.press('Space');
   await allRatings(page);await page.keyboard.press('1');await page.getByRole('heading',{name:'오늘 목록을 마쳤어요'}).waitFor();
   await page.getByText('학습 기록·남은 범위',{exact:true}).click();assert.match(await page.getByRole('region',{name:'Main Quiz 학습 현황'}).innerText(),/고유 목표 3개 · 첫 학습 2/);
   assert.deepEqual(errors,[]);
 }catch(error){await screenshot(page,'failure');console.error((await page.locator('body').innerText()).slice(0,3500));throw error;}finally{await browser.close();}
});

test('map from start, PDF failure and modal do not block four self-ratings',async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try{
   const context=await contextFor(browser,{extraHTTPHeaders:{'X-Root-Test-User':'map-first'}}),page=await context.newPage();
   await context.route('**/api/root-learning/sessions/*/map',async route=>{
     const response=await route.fetch(),map=await response.json();
     map.concepts.push(...Array.from({length:126},(_,i)=>({concept_id:'large-'+i,label:'Synthetic concept '+i,parent_ids:[]})));
     map.currentConceptIds=['A'];return route.fulfill({json:map});
   });
   await page.goto(url);await page.getByRole('button',{name:'개념 지도',exact:true}).click();await page.getByRole('heading',{name:'개념 지도',exact:true}).waitFor();
   // Concepts that anchor no question (answer nodes, extra labels) are not tree nodes: lecture + 3 topics, and the current topic's question row.
   const graph=page.getByRole('group',{name:'개념 트리'});assert.equal(await graph.getByRole('button').count(),5);
   assert.equal(await graph.getByRole('button',{name:/현재 문제$/}).count(),1);
   await page.getByRole('searchbox').fill('Synthetic target 3');await page.locator('.main-quiz-map-search li button').filter({hasText:'Synthetic target 3'}).click();
   await page.getByRole('complementary',{name:'선택한 항목'}).getByRole('heading',{name:'Synthetic target 3'}).waitFor();
   const before=await graph.getAttribute('style');await page.getByRole('button',{name:'확대',exact:true}).click();
   assert.notEqual(await graph.getAttribute('style'),before);
   assert.equal(await page.locator('.main-quiz-tree-frame').evaluate(e=>e.clientHeight<=640),true);
   await page.getByRole('button',{name:'← 문제로 돌아가기'}).click();await enabled(page,'답 보기');await page.getByRole('button',{name:/^답 보기/}).click();await allRatings(page);
   await page.getByRole('img',{name:'two-pages.pdf · PDF 2쪽',exact:true}).waitFor();await page.getByRole('button',{name:'two-pages.pdf · PDF 2쪽 크게 보기'}).click();
   await page.getByRole('dialog').waitFor();await page.keyboard.press('3');assert.match(await page.getByRole('heading',{name:/문항/}).innerText(),/1 \/ 3/);
   await page.keyboard.press('Escape');await page.getByRole('heading',{name:'문항 1 / 3'}).focus();await page.keyboard.press('4');await page.getByText('Synthetic question 2?',{exact:true}).waitFor();
   await context.close();
   const failure=await contextFor(browser,{extraHTTPHeaders:{'X-Root-Test-User':'pdf-failure'}});await failure.route('**/api/root-learning/lectures/*/*/sources/**',r=>r.fulfill({status:404,body:'missing fixture'}));
   const broken=await failure.newPage();await broken.goto(url);await broken.getByRole('button',{name:'오늘 학습 시작'}).click();await enabled(broken,'답 보기');await broken.getByRole('button',{name:/^답 보기/}).click();
   await broken.getByRole('alert').filter({hasText:'참고 슬라이드를 불러오지 못했습니다.'}).waitFor();await allRatings(broken);
   assert.match(await broken.getByRole('link',{name:'원본 열기',exact:true}).getAttribute('href'),/#page=2$/);await failure.close();
 }finally{await browser.close();}
});

test('blocked storage and malformed requests prevent untracked writes',async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});let posts=0;
 try{
  const context=await contextFor(browser,{extraHTTPHeaders:{'X-Root-Test-User':'storage-user'}});
  await context.route('**/api/root-learning/lectures/test/demo/sessions',route=>{if(route.request().method()==='POST')posts++;return route.continue();});
  const page=await context.newPage();await page.goto(url);await page.getByRole('button',{name:'오늘 학습 시작'}).waitFor();
  await page.evaluate(()=>{Storage.prototype.setItem=()=>{throw new Error('Storage blocked');};});await page.getByRole('button',{name:'오늘 학습 시작'}).click();
  await page.getByRole('alert').filter({hasText:'이 브라우저에 보관하지 못했습니다.'}).waitFor();assert.equal(posts,0);await context.close();
  const corrupt=await contextFor(browser,{extraHTTPHeaders:{'X-Root-Test-User':'corrupt-user'}});const key='studyez:root-write:["","test","demo"]:broken';
  await corrupt.addInitScript(key=>localStorage.setItem(key,'{broken'),key);const broken=await corrupt.newPage();await broken.goto(url);
  await broken.getByRole('alert').filter({hasText:'원본을 보존했으며 새 저장은 중지했습니다.'}).waitFor();
  assert.equal(await broken.getByRole('button',{name:'오늘 학습 시작'}).isDisabled(),true);assert.equal(await broken.evaluate(key=>localStorage.getItem(key),key),'{broken');await corrupt.close();
 }finally{await browser.close();}
});

test('answers and next questions draw at once while saving is slow; PDF reads ranges only',async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try{
  const context=await contextFor(browser,{extraHTTPHeaders:{'X-Root-Test-User':'slow-save'}});
  const sources=[];let sessionReads=0;
  await context.route('**/api/root-learning/sessions/*/events',async route=>{await new Promise(r=>setTimeout(r,1500));return route.continue();});
  context.on('request',request=>{
    if(request.method()!=='GET')return;
    if(/\/api\/root-learning\/lectures\/[^/]+\/[^/]+\/sources\//.test(request.url()))sources.push(request.headers()['range']??'');
    if(/\/api\/root-learning\/sessions\/[^/?]+$/.test(request.url()))sessionReads++;
  });
  const page=await context.newPage();
  const prepared=page.waitForResponse(r=>r.url().includes('/prepare?')&&r.status()===200);
  await page.goto(url);await page.getByRole('button',{name:'오늘 학습 시작'}).click();await enabled(page,'답 보기');await prepared;
  await page.getByRole('img',{name:'two-pages.pdf · PDF 2쪽',exact:true}).count();
  const quick=async(step,ready)=>{const t=Date.now();await step();await ready();const ms=Date.now()-t;assert.ok(ms<1000,`drew in ${ms}ms, not after the 1.5s save`);};
  await page.getByRole('heading',{name:'문항 1 / 3'}).focus();
  await quick(()=>page.keyboard.press('Space'),()=>enabled(page,'Good'));
  await page.getByRole('img',{name:'two-pages.pdf · PDF 2쪽',exact:true}).waitFor();
  const reads=sessionReads;
  await quick(()=>page.keyboard.press('3'),()=>page.getByText('Synthetic question 2?',{exact:true}).waitFor());
  await quick(()=>page.keyboard.press('Space'),()=>enabled(page,'Good'));
  await quick(()=>page.keyboard.press('2'),()=>page.getByText('Synthetic question 3?',{exact:true}).waitFor());
  assert.equal(sessionReads,reads,'no session read between actions');
  await page.keyboard.press('Space');await enabled(page,'Easy');await page.keyboard.press('4');
  await page.getByRole('heading',{name:'오늘 목록을 마쳤어요'}).waitFor();
  await page.getByText('학습 기록·남은 범위',{exact:true}).click();
  assert.match(await page.getByRole('region',{name:'Main Quiz 학습 현황'}).innerText(),/고유 목표 3개 · 첫 학습 2 · 회상 가능 1/);
  assert.equal(await page.evaluate(()=>Object.keys(localStorage).filter(k=>k.startsWith('studyez:root-write:')).length),0,'every write confirmed');
  assert.ok(sources.length>0);assert.deepEqual(sources.filter(r=>!/^bytes=\d+-\d+$/.test(r)),[],'no full-file GET of the PDF');
  await context.close();
 }finally{await browser.close();}
});
