const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const crypto=require('node:crypto');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');

test('actual Markdown file selects the lecture, validates before saving and retains bytes through retry',async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try {
  const page=await browser.newPage();
  const requests=[];let fail=true;
  await page.route('**/bank/shared-source',route=>route.fulfill({status:404,contentType:'application/json',body:'{}'}));
  await page.route('**/bank-response',async route=>{
   requests.push(route.request().postDataJSON());
   await route.fulfill({status:fail?409:200,contentType:'application/json',body:JSON.stringify(fail?{detail:'검수 중'}:{jobId:1})});
  });
  await page.goto(`${process.env.STUDY_TEST_URL||'http://127.0.0.1:5199'}/tests/bank-response.html`);
  await page.getByText('답변 직접 붙여넣기',{exact:true}).click();
  const picker=page.getByLabel('완성된 문제은행 .md 파일 불러오기');
  const source=fs.readFileSync(path.join(__dirname,'../../tests/fixtures/bank-file-valid.md'),'utf8');
  await picker.setInputFiles({name:'study-ez-261006_02-bank.md',mimeType:'text/markdown',buffer:Buffer.from(source)});
  await page.getByRole('alert').waitFor();assert.equal(requests.length,0);
  const raw='\ufeff'+source.replace(/261006_02/g,'261016_03').replace(/\n/g,'\r\n');
  await picker.setInputFiles({name:'study-ez-261016_03-bank.md',mimeType:'text/markdown',buffer:Buffer.from(raw)});
  await page.getByText(/8문항.*파일 확인 완료/).waitFor();
  const save=page.getByRole('button',{name:'답변 저장·검수 요청'});
  await save.click();await page.getByRole('alert').waitFor();
  assert.equal(requests[0].raw,raw);
  assert.equal(requests[0].responseFile.sha256,crypto.createHash('sha256').update(raw).digest('hex'));
  assert.equal(requests[0].source,'manual');assert.equal(requests[0].promptVersion,'1.76');
  fail=false;await save.click();await page.getByRole('status').waitFor();
  assert.deepEqual(requests[0],requests[1]);
 }finally{await browser.close();}
});
