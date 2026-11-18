const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');const path=require('node:path');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const url=process.env.JOKBO_MIX_URL||'http://127.0.0.1:5199/tests/jokbo-mix.html';
const output=process.env.ROOT_TEST_OUTPUT;
async function shot(page,name){if(output){fs.mkdirSync(output,{recursive:true});await page.screenshot({path:path.join(output,'jokbo-mix-'+name+'.png'),fullPage:true});}}

async function launch(user){
  const browser=await chromium.launch({headless:true,channel:process.env.PLAYWRIGHT_CHANNEL||'chrome'});
  const context=await browser.newContext({viewport:{width:1360,height:900},extraHTTPHeaders:{'X-Root-Test-User':user}});
  context.setDefaultTimeout(15000);
  await context.route('**/api/me',r=>r.fulfill({json:{id:user,email:user+'@example.com',isApproved:true,isAdmin:false}}));
  const page=await context.newPage();
  const writes=[];
  page.on('request',r=>{if(['POST','PUT'].includes(r.method())&&r.url().includes('/api/jokbo/events/'))writes.push(r.method()+' '+new URL(r.url()).pathname);});
  return {browser,page,writes};
}
const counted=page=>page.waitForFunction(()=>{const t=document.querySelector('#jokbo-mix-lectures')?.textContent;return t&&!t.includes('…');});
const rows=page=>page.getByRole('list',{name:'고른 강의'});
const startCount=page=>page.locator('.mq-start-button .mq-card-count').innerText();
const globalChip=(page,label)=>page.getByRole('group',{name:'교수',exact:true}).getByRole('button',{name:new RegExp('^'+label)});
const laneChip=(page,lecture,label)=>page.getByRole('group',{name:`${lecture} 교수`}).getByRole('button',{name:new RegExp('^'+label)});
const stem=page=>page.locator('.jokbo-stem').first().innerText();
async function step(page){return page.locator('.pq-count').innerText();}
/** Pick a choice (reveal), then rate with Enter (suggested band). */
async function solve(page,choice='1'){
  await page.locator('.jokbo-reveal').waitFor();
  await page.keyboard.press(choice);
  await page.locator('.jokbo-rate').first().waitFor();
  await page.keyboard.press('Enter');
}

test('족보 모아풀기: 범위 칩(전체·강의별·같은 교수 없는 강의), 강의 수에 맞춘 배분, 기록은 각 칸으로, Z, 회독',async()=>{
  const {browser,page,writes}=await launch('a');const errors=[];page.on('pageerror',e=>errors.push(e.message));
  try{
    await page.goto(url+'?e=evA&e=evB&e=evC&e=nope');
    await page.getByRole('heading',{name:'족보 모아풀기 · 4개 강의'}).waitFor();
    await counted(page);
    assert.match(await rows(page).innerText(),/Lecture A[\s\S]*6문항[\s\S]*Lecture B[\s\S]*2문항[\s\S]*Lecture C[\s\S]*1문항[\s\S]*nope[\s\S]*족보 없음/);
    assert.equal(await startCount(page),'9');
    assert.equal(await globalChip(page,'같은 교수만').getAttribute('aria-pressed'),'true');
    assert.match(await globalChip(page,'같은 교수만').innerText(),/9/);
    assert.match(await globalChip(page,'다른 교수까지').innerText(),/12/);

    // 강의별: C has no same-professor items. Switching B alone makes both overall chips 「일부」.
    await page.getByRole('button',{name:'강의별'}).click();
    assert.equal(await laneChip(page,'Lecture C','같은 교수만').isDisabled(),true);
    assert.match(await laneChip(page,'Lecture C','같은 교수만').innerText(),/같은 교수만\s*0/);
    assert.equal(await laneChip(page,'Lecture C','다른 교수까지').getAttribute('aria-pressed'),'true');
    await laneChip(page,'Lecture B','다른 교수까지').click();
    assert.equal(await startCount(page),'10');
    assert.equal(await globalChip(page,'같은 교수만').getAttribute('aria-pressed'),'mixed');
    assert.equal(await globalChip(page,'다른 교수까지').getAttribute('aria-pressed'),'mixed');
    await shot(page,'start-per-lecture');
    await globalChip(page,'다른 교수까지').click();
    assert.equal(await startCount(page),'12');
    await globalChip(page,'같은 교수만').click();
    assert.equal(await startCount(page),'9');

    // 모아풀기: each lecture keeps its order and is spread by its size (k+½)/n — not round-robin.
    await page.getByRole('button',{name:/^시작/}).click();
    const seen=[];
    const expected=['A question 1?','A question 2?','B question 1?','A question 3?','C question 1?',
      'A question 4?','A question 5?','B question 2?','A question 6?'];
    for(let i=0;i<expected.length;i++){
      assert.equal(await step(page),`족보 ${i+1} / 9`);
      const s=await stem(page);seen.push(s);
      const lecture=s[0];
      assert.equal(await page.locator('.pq-title').innerText(),`Lecture ${lecture}`);
      if(i===0){
        // Z after rating goes back to the answer screen of that question.
        await solve(page,'2');
        assert.equal(await step(page),'족보 2 / 9');
        await page.keyboard.press('z');
        await page.locator('.jokbo-rate').first().waitFor();
        assert.equal(await step(page),'족보 1 / 9');
        await page.keyboard.press('Enter');
        continue;
      }
      await solve(page);
    }
    assert.deepEqual(seen,expected);
    await page.getByRole('heading',{name:'족보 완료'}).waitFor();
    assert.equal(await page.locator('.pq-title').innerText(),'족보 모아풀기 · 3개 강의');
    await shot(page,'done');
    // Each answer went to its own cell with the original item ID; one round per lecture in the range.
    await new Promise(r=>setTimeout(r,500));
    const answers=writes.filter(w=>w.endsWith('/answer'));
    assert.equal(answers.length,9);
    assert.ok(answers.includes('POST /api/jokbo/events/evC/items/c1/answer'),answers.join('\n'));
    assert.ok(answers.includes('POST /api/jokbo/events/evB/items/b2/answer'));
    assert.deepEqual(writes.filter(w=>w.endsWith('/rounds')).sort(),
      ['POST /api/jokbo/events/evA/rounds','POST /api/jokbo/events/evB/rounds','POST /api/jokbo/events/evC/rounds']);
    // The first question was wrong: it is in the wrong-note list on the done screen.
    assert.match(await page.locator('.jokbo-kept').innerText(),/A question 1\?/);

    await page.goto(url+'?e=evA&e=evB&e=evC');
    await counted(page);
    await page.setViewportSize({width:390,height:844});
    await page.getByRole('button',{name:'강의별'}).click();
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
    await shot(page,'start-mobile');
    assert.deepEqual(errors,[]);
  }catch(error){await shot(page,'failure');console.error((await page.locator('body').innerText()).slice(0,3000));throw error;}
  finally{await browser.close();}
});

test('족보 모아풀기 섞어풀기: 모든 문항을 한 번씩',async()=>{
  const {browser,page}=await launch('b');const errors=[];page.on('pageerror',e=>errors.push(e.message));
  try{
    await page.goto(url+'?e=evA&e=evB&e=evC');
    await counted(page);
    await globalChip(page,'다른 교수까지').click();
    await page.getByRole('radio',{name:'섞어풀기'}).click();
    await page.getByRole('button',{name:/^시작/}).click();
    const seen=[];
    for(let i=0;i<12;i++){seen.push(await stem(page));await solve(page);}
    await page.getByRole('heading',{name:'족보 완료'}).waitFor();
    const all=[...[1,2,3,4,5,6,7,8].map(i=>`A question ${i}?`),...[1,2,3].map(i=>`B question ${i}?`),'C question 1?'];
    assert.deepEqual([...seen].sort(),all.sort());
    console.log('섞어풀기 순서:',seen.join(' → '));
    assert.deepEqual(errors,[]);
  }catch(error){await shot(page,'failure-shuffle');console.error((await page.locator('body').innerText()).slice(0,3000));throw error;}
  finally{await browser.close();}
});
