const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const source=fs.readFileSync(path.join(__dirname,'../../bridge/bank-download.js'),'utf8');
const raw=fs.readFileSync(path.join(__dirname,'../fixtures/bank-file-valid.md'),'utf8');
const target={subject:'약리학',runId:'261006_02',promptVersion:'1.76',filename:'study-ez-261006_02-bank.md'};

function page(onClick, anchors=[]) {
 const urls={createObjectURL:()=> 'blob:actual-file'};const original=urls.createObjectURL;let clicks=0;
 const button={disabled:false,getBoundingClientRect:()=>({width:20}),getAttribute:name=>name==='aria-label'?'파일 다운로드':null,
  click(){clicks++;onClick?.(urls);}};
 const parent={parentElement:null,querySelectorAll:()=>[button]};
 const preview={parentElement:parent,getAttribute:()=>target.filename+' 미리보기 열기'};
 const ctx=vm.createContext({URL:urls,Reflect,TextDecoder,setTimeout,clearTimeout,location:{pathname:'/c/existing'},
  document:{querySelectorAll:s=>s==='button[aria-label]'?[preview]:anchors}});
 vm.runInContext(source,ctx);
 return{ctx,urls,original,get clicks(){return clicks;}};
}

test('captures exact UTF-8 bytes from the actual filename-bound download control and restores the hook',async()=>{
 const p=page(urls=>urls.createObjectURL(new Blob([raw])));
 const got=await p.ctx.captureBankDownload(target,'existing',100);
 assert.equal(got.raw,raw);assert.equal(got.filename,target.filename);assert.equal(p.clicks,1);
 assert.equal(p.urls.createObjectURL,p.original);
});

test('unrelated files and other lectures never leave the page',async()=>{
 const p=page(urls=>{
  urls.createObjectURL(new Blob(['unrelated private content'.repeat(20)]));
  urls.createObjectURL(new Blob([raw.replaceAll('261006_02','other')]));
 });
 const got=await p.ctx.captureBankDownload(target,'existing',20);
 assert.ok(got.error);assert.equal(got.raw,undefined);assert.equal(p.urls.createObjectURL,p.original);
});

test('rejects a different conversation without clicking or installing hooks',async()=>{
 const p=page();const got=await p.ctx.captureBankDownload(target,'different',20);
 assert.ok(got.error);assert.equal(p.clicks,0);assert.equal(p.urls.createObjectURL,p.original);
});

test('a valid target wins even when unrelated blobs are created before the real file',async()=>{
 const p=page(urls=>{
  urls.createObjectURL(new Blob(['x'.repeat(400)]));
  urls.createObjectURL(new Blob([raw]));
 });
 assert.equal((await p.ctx.captureBankDownload(target,'existing',100)).raw,raw);
});
