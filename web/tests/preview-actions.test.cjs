const {test, before, after} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {pathToFileURL} = require('node:url');
const root = path.resolve(__dirname, '../..');
const web = path.join(root, 'web');
const bundled = path.join(require('node:os').homedir(), '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || (fs.existsSync(bundled) ? bundled : 'playwright'));
const bridgeSource = fs.readFileSync(path.join(root, 'bridge/chatgpt-bridge.js'), 'utf8').replace('void initialize();', '');
let server, browser, origin;
before(async () => {
  const {createServer} = await import(pathToFileURL(require.resolve('vite', {paths:[web]})));
  const {default: react} = await import(pathToFileURL(require.resolve('@vitejs/plugin-react', {paths:[web]})));
  server = await createServer({root:web, configFile:false, plugins:[react()],
    server:{host:'127.0.0.1', port:5197, strictPort:true, fs:{allow:[root]}}});
  await server.listen();
  origin = `http://127.0.0.1:${server.httpServer.address().port}`;
  browser = await chromium.launch({headless:true, channel:'chrome'});
});
after(async () => { await browser?.close(); await server?.close(); });

function extension() {
  const stored = {}; let receive, tabId = 10;
  const context = vm.createContext({URL, console, importScripts(){}, chrome:{
    runtime:{onMessage:{addListener(fn){receive=fn;}}, onConnect:{addListener(){}}},
    storage:{session:{async get(key){return key === null ? {...stored} : {[key]:stored[key]};},
      async set(values){Object.assign(stored, values);}, async remove(keys){for(const key of [].concat(keys)) delete stored[key];}}},
    tabs:{onUpdated:{addListener(){}},onActivated:{addListener(){}},onRemoved:{addListener(){}},
      async create(){return {id:tabId++};}, async sendMessage(){}},
  }});
  for (const file of ['protocol.js','background.js']) vm.runInContext(fs.readFileSync(path.join(root,'bridge',file),'utf8'), context);
  const send = (message, sender) => new Promise(resolve => {
    if (!receive(message, sender, resolve)) resolve({ok:false});
  });
  return {stored, send, async launch(payload) {
    const id=tabId;
    const result=await send({type:'STUDYEZ_OPEN_PREVIEW',payload}, {tab:{id:1,url:'http://localhost:5173'}});
    assert.equal(result.ok,true);
    return {tab:{id,url:'https://chatgpt.com/'}};
  }};
}
const request = (id, autoSend=true) => ({requestId:id,lectureId:`test/${id}`,provider:'chatgpt',mode:'shared',autoSend,
  prompt:`${id}.pdf\n이번 강의 예습을 설명해줘.`,files:[{id:'notes',filename:`${id}.pdf`,
    downloadUrl:'http://localhost:8000/api/local-storage/lectures/fixture.pdf'}]});

async function composer(ext, payload, options={}) {
  const sender=await ext.launch(payload);
  const page=await browser.newPage();
  await page.exposeFunction('extensionMessage', message => ext.send(message,sender));
  await page.route('**/draft-fixture', route => route.fulfill({contentType:'text/html',body:'<!doctype html><meta charset="utf-8"><body></body>'}));
  await page.goto(origin+'/draft-fixture');
  await page.evaluate(({payload,options}) => {
    const nativeTimeout=setTimeout, nativeNow=Date.now, clockStart=nativeNow();
    // Accelerate only the synthetic fixture; no AI website is opened.
    Date.now=()=>clockStart+(nativeNow()-clockStart)*20;
    window.setTimeout=(fn,ms,...args)=>nativeTimeout(fn,ms===3000?5:ms===250?20:ms===100?5:ms,...args);
    const state=window.fixture={downloads:0,attached:0,clicks:0,options,attachments:options.attachments||[]};
    const inputMarkup=options.editorType==='textarea' ? '<textarea id="prompt-textarea"></textarea>' :
      '<rich-textarea><div id="prompt-textarea" class="ProseMirror" contenteditable="true" style="min-height:50px"></div></rich-textarea>';
    document.body.innerHTML='<form><div id="attachments"></div>'+inputMarkup+
      '<input type="file" multiple hidden><button type="button" aria-label="업로드 및 도구">Files</button>'+
      '<button type="button" data-test-id="local-images-files-uploader-button">Upload</button>'+
      '<button type="button" data-testid="send-button" aria-label="보내기">Send</button></form>';
    const editor=()=>document.querySelector('#prompt-textarea');
    if(options.editorType==='textarea')editor().value=options.text||'';
    else editor().textContent=options.text||'';
    const render=()=>{
      document.querySelector('#attachments').replaceChildren();
      for(const name of state.attachments){
        const card=document.createElement('div');
        card.textContent=name;
        const remove=document.createElement('button');remove.type='button';remove.setAttribute('aria-label',`${name} 제거`);remove.textContent='×';
        remove.onclick=()=>{if(options.cannotRemove)return; state.attachments.splice(state.attachments.indexOf(name),1);render();
          if(options.remountOnRemove)editor().replaceWith(editor().cloneNode(true));};
        card.append(remove);document.querySelector('#attachments').append(card);
      }
      if(options.uploadFails&&state.attached){const error=document.createElement('div');error.textContent='업로드 실패';document.querySelector('#attachments').append(error);}
    };
    render();
    document.querySelector('input').onchange=event=>{state.attached++;state.attachments=[...event.target.files].map(f=>f.name);render();};
    document.querySelector('[data-testid=send-button]').onclick=()=>{state.clicks++;if(!options.unconfirmed)editor().textContent='';};
    const consentKey=`studyez-consent:${payload.autoSend?'auto-v1':'manual-v1'}:${payload.provider}:shared`;
    window.chrome={storage:{local:{get(_key,cb){cb({[consentKey]:true});},async set(){},async remove(){}}},runtime:{
      sendMessage(message,cb){if(message.type==='STUDYEZ_GET_PAYLOAD')cb({ok:true,payload});
        else if(message.type==='STUDYEZ_PREPARE_GEMINI_FILE_INPUT')cb({ok:true});
        else window.extensionMessage(message).then(cb);},
      connect(){let onMessage;return {onMessage:{addListener(fn){onMessage=fn;}},onDisconnect:{addListener(){}},disconnect(){},
        postMessage(message){state.downloads++;nativeTimeout(()=>{
          if(options.editDuringDownload)editor().textContent='사용자가 새로 쓴 내용';
          onMessage({type:'FILE_CHUNK',fileId:message.fileId,chunk:btoa('Synthetic lecture PDF')});
          onMessage({type:'FILE_END',fileId:message.fileId});
        },30);}};},
    }};
  }, {payload,options});
  await page.addScriptTag({content:bridgeSource});
  await page.evaluate(()=>initialize());
  return page;
}
const recovery = page => page.locator('[data-action=recover]');
const line = page => page.locator('.studyez-status');
const state = page => page.evaluate(()=>({text:editorText(document.querySelector('#prompt-textarea')),
  ...window.fixture,options:undefined}));

for(const provider of ['chatgpt','gemini','claude'])
for(const editorType of ['contenteditable','textarea'])
test(`${provider}/${editorType}: previous prompt is replaced exactly once without recovery`,async()=>{
  const payload={...request('current',false),provider};
  const page=await composer(extension(),payload,{text:'Old prompt\n이전 강의 프롬프트',editorType});
  try {
    await page.getByRole('button',{name:'자료·프롬프트 넣기',exact:true}).click();
    await page.waitForFunction(()=>document.querySelector('.studyez-status').textContent.includes('직접 전송해 주세요'));
    const result=await state(page);
    assert.equal(result.text,payload.prompt);
    assert.equal(result.attached,1);assert.equal(result.clicks,0);
    assert.equal(await recovery(page).isVisible(),false);
  } finally {await page.close();}
});

test('automatic input replaces previous text and submits only the new prompt',async()=>{
  const page=await composer(extension(),request('current'),{text:'Previous lecture prompt'});
  try {
    await page.waitForFunction(()=>document.querySelector('.studyez-status').textContent.includes('전송했습니다'));
    const result=await state(page);assert.equal(result.clicks,1);assert.equal(result.text,'');
    assert.equal(await recovery(page).isVisible(),false);
  } finally {await page.close();}
});

test('an identical prompt is replaced without duplication',async()=>{
  const payload=request('current',false),page=await composer(extension(),payload,{text:payload.prompt});
  try {
    await page.getByRole('button',{name:'자료·프롬프트 넣기',exact:true}).click();
    await page.waitForFunction(()=>document.querySelector('.studyez-status').textContent.includes('직접 전송해 주세요'));
    assert.equal((await state(page)).text,payload.prompt);
  } finally {await page.close();}
});

test('replacement stops when text changes during download without old attachments',async()=>{
  const page=await composer(extension(),request('current'),{text:'Previous prompt',editDuringDownload:true});
  try {
    await page.waitForFunction(()=>/바뀌/.test(document.querySelector('.studyez-status').textContent));
    const result=await state(page);assert.equal(result.text,'사용자가 새로 쓴 내용');
    assert.equal(result.clicks,0);assert.equal(result.attached,0);
  } finally {await page.close();}
});

test('preview primary card creates a shared manual request; only the separate tool auto-sends', async () => {
  const page=await browser.newPage();
  const errors=[];page.on('pageerror',error=>errors.push(error.message));
  try {
    await page.goto(origin+'/tests/shared-preview-prompt.html');
    await page.getByRole('button',{name:'공통 대화 만들기',exact:true}).click({timeout:5000}).catch(async error=>{
      throw new Error(`${error.message}\nFixture errors: ${errors.join('; ')}\n${await page.locator('body').innerText()}`);
    });
    await page.waitForFunction(()=>window.promptTest.sent.length===1);
    const first=await page.evaluate(()=>window.promptTest.sent[0]);
    assert.equal(first.mode,'shared');assert.equal(first.autoSend,false);assert.equal(first.files.length,1);
    await page.getByRole('button',{name:'기본 링크 생성 · 첨부 후 자동 전송 (관리자)'}).click();
    await page.waitForFunction(()=>window.promptTest.sent.length===2);
    assert.equal(await page.evaluate(()=>window.promptTest.sent[1].autoSend),true);
    await page.goto(origin+'/tests/shared-preview-prompt.html?student');
    await page.getByRole('button',{name:'내 예습 프롬프트 고치기'}).waitFor({timeout:5000}).catch(async error=>{
      throw new Error(`${error.message}\nFixture errors: ${errors.join('; ')}\n${await page.locator('body').innerText()}`);
    });
    assert.equal(await page.getByRole('button',{name:'공통 대화 만들기',exact:true}).count(),0);
    await page.goto(origin+'/tests/shared-preview-prompt.html?noExtension');
    await page.getByText('확장을 설치하면 만듭니다').waitFor();
    assert.equal(await page.getByRole('button',{name:'공통 대화 만들기',exact:true}).count(),0);
  } finally {await page.close();}
});

test('screenshot case preserves the old lecture until explicit recovery, then sends the current lecture once', async () => {
  const page=await composer(extension(),request('심내막염'),{text:'무산소성세균.pdf\n이전 강의 예습',attachments:['무산소성세균.pdf','이전 족보.md'],remountOnRemove:true});
  try {
    await recovery(page).waitFor({state:'visible'});
    assert.equal((await state(page)).downloads,0);
    assert.match((await state(page)).text,/무산소성세균/);
    if(process.env.PREVIEW_TEST_OUTPUT){
      fs.mkdirSync(process.env.PREVIEW_TEST_OUTPUT,{recursive:true});
      await page.screenshot({path:path.join(process.env.PREVIEW_TEST_OUTPUT,'draft-recovery.png')});
    }
    await recovery(page).evaluate(button=>{button.click();button.click();});
    await page.waitForFunction(()=>document.querySelector('.studyez-status').textContent.includes('전송했습니다'));
    const result=await state(page);
    assert.equal(result.clicks,1);assert.equal(result.attached,1);assert.equal(result.downloads,1);
    assert.deepEqual(result.attachments,['심내막염.pdf']);
    assert.equal(result.text,'');
  } finally {await page.close();}
});

test('manual input replaces previous text by default without submitting or recovery', async () => {
  const page=await composer(extension(),request('current',false),{text:'이전 초안'});
  try {
    await page.getByRole('button',{name:'자료·프롬프트 넣기',exact:true}).click();
    await page.waitForFunction(()=>document.querySelector('.studyez-status').textContent.includes('직접 전송해 주세요'));
    const result=await state(page);assert.equal(result.clicks,0);assert.equal(result.attached,1);
    assert.equal(result.text,request('current',false).prompt);
    assert.equal(await recovery(page).isVisible(),false);
  } finally {await page.close();}
});

for(const options of [{text:'이전 초안',attachments:['이전.pdf']}, {text:'',attachments:['알 수 없는 사진.png']}])
test(`cancel preserves a conflicting draft and attachments: ${JSON.stringify(options)}`,async()=>{
  const page=await composer(extension(),request('current'),options);
  try {
    await recovery(page).waitFor({state:'visible'});await page.locator('[data-action=cancel]').click();
    assert.equal((await state(page)).text,options.text);assert.equal((await state(page)).downloads,0);
    assert.deepEqual((await state(page)).attachments,options.attachments||[]);
  } finally {await page.close();}
});

for(const duringDownload of [false,true])
test(`editing before recovery completes preserves new text (during download=${duringDownload})`,async()=>{
  const page=await composer(extension(),request('current'),{text:'이전 초안',attachments:['이전.pdf'],editDuringDownload:duringDownload});
  try {
    await recovery(page).waitFor({state:'visible'});
    if(!duringDownload)await page.locator('#prompt-textarea').fill('사용자가 새로 쓴 내용');
    await recovery(page).click();
    await page.waitForFunction(()=>/바뀌/.test(document.querySelector('.studyez-status').textContent));
    const result=await state(page);assert.equal(result.text,'사용자가 새로 쓴 내용');assert.equal(result.clicks,0);assert.equal(result.attached,0);
  } finally {await page.close();}
});

test('a known, unchanged failed draft is claimed across requests without another recovery click',async()=>{
  const ext=extension(), old=request('old');
  const prior=await composer(ext,old,{uploadFails:true});
  try {
    await prior.waitForFunction(()=>document.querySelector('.studyez-status').textContent.includes('업로드에 실패'));
    for(let i=0;i<50&&!Object.keys(ext.stored).some(k=>k.startsWith('studyez-draft:'));i++)await new Promise(r=>setTimeout(r,10));
    assert.equal(Object.keys(ext.stored).filter(k=>k.startsWith('studyez-draft:')).length,1);
    const proof=Object.entries(ext.stored).find(([k])=>k.startsWith('studyez-draft:'))[1];
    assert.match(proof.fingerprint,/^[a-f0-9]{64}$/);assert.equal('text' in proof,false);
    const page=await composer(ext,request('new'),{text:old.prompt,attachments:['old.pdf']});
    try {
      await page.waitForFunction(()=>document.querySelector('.studyez-status').textContent.includes('전송했습니다'));
      assert.equal((await state(page)).clicks,1);assert.deepEqual((await state(page)).attachments,['new.pdf']);
      assert.equal(await recovery(page).isVisible(),false);
      assert.equal(Object.keys(ext.stored).filter(k=>k.startsWith('studyez-draft:')).length,0);
    } finally {await page.close();}
  } finally {await prior.close();}
});

for(const change of ['text','attachment'])
test(`editing a failed draft revokes automatic ownership proof (${change})`,async()=>{
  const ext=extension(),old=request('old');const prior=await composer(ext,old,{uploadFails:true});
  try {
    await prior.waitForFunction(()=>document.querySelector('.studyez-status').textContent.includes('업로드에 실패'));
    for(let i=0;i<50&&!Object.keys(ext.stored).some(k=>k.startsWith('studyez-draft:'));i++)await new Promise(r=>setTimeout(r,10));
    if(change==='text')await prior.locator('#prompt-textarea').fill('내가 수정한 초안');
    else await prior.getByRole('button',{name:'old.pdf 제거',exact:true}).click();
    // The exposed Chrome callback crosses the browser/Node process boundary.
    for(let i=0;i<50&&Object.keys(ext.stored).some(k=>k.startsWith('studyez-draft:'));i++)await new Promise(r=>setTimeout(r,10));
    assert.equal(Object.keys(ext.stored).filter(k=>k.startsWith('studyez-draft:')).length,0);
    const page=await composer(ext,request('new'),{text:old.prompt,attachments:['old.pdf']});
    try {await recovery(page).waitFor({state:'visible'});assert.equal((await state(page)).downloads,0);}
    finally {await page.close();}
  } finally {await prior.close();}
});

test('uncertain submission never offers recovery, records ownership or clicks send twice',async()=>{
  const ext=extension(),page=await composer(ext,request('current'),{unconfirmed:true});
  try {
    await page.waitForFunction(()=>document.querySelector('.studyez-status').textContent.includes('접수 여부를 확인하지 못했습니다'));
    assert.equal((await state(page)).clicks,1);assert.equal(await recovery(page).isVisible(),false);
    assert.equal(Object.keys(ext.stored).filter(k=>k.startsWith('studyez-draft:')).length,0);
  } finally {await page.close();}
});

test('an attachment that cannot be removed prevents replacement and send',async()=>{
  const page=await composer(extension(),request('current'),{text:'이전 초안',attachments:['old.pdf'],cannotRemove:true});
  try {
    await recovery(page).waitFor({state:'visible'});await recovery(page).click();
    await page.waitForFunction(()=>document.querySelector('.studyez-status').textContent.includes('첨부 제거를 확인하지 못했습니다'));
    assert.equal((await state(page)).text,'이전 초안');assert.equal((await state(page)).clicks,0);assert.equal((await state(page)).attached,0);
  } finally {await page.close();}
});
