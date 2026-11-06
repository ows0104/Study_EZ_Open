const {test}=require('node:test');const assert=require('node:assert/strict');
const fs=require('node:fs');const path=require('node:path');const vm=require('node:vm');const crypto=require('node:crypto');const ts=require('typescript');
const root=path.resolve(__dirname,'../..');
const guidance=fs.readFileSync(path.join(root,'content/prompts/learning-links/automation/web-author.md'),'utf8');
const compiled=ts.transpileModule(fs.readFileSync(path.join(root,'web/src/bank/rootWeb.ts'),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText;
function fixture(send){
 const calls=[],requests=[];const exports={};
 vm.runInNewContext(compiled,{exports,crypto:crypto.webcrypto,TextEncoder,require:id=>{
   if(id.endsWith('?raw'))return {default:guidance};
   if(id==='../api')return {api:async(url,init)=>{
     calls.push({url,init});return init?{send}:{packet:{subject:'test',runId:'demo',title:'Synthetic',inputMode:'source',scope:'Approved scope',sources:[{assetId:'S1',filename:'source.pdf',downloadUrl:'http://127.0.0.1/source'}]}};
   }};
   if(id==='../bridge/previewBridge')return {extensionCompatible:()=>true,extensionInputMinimum:()=>'',absoluteUrl:x=>x,requestPreview:async request=>requests.push(request)};
   if(id==='./prompt')return {loadLatestBankPrompt:async()=>({version:'1.82',prompt:'Canonical prompt unchanged'})};
   if(id==='./responseFile')return {};
   throw Error(id);
 }});return {sendRootWeb:exports.sendRootWeb,calls,requests};
}
test('Main Quiz dispatch includes recall guidance and freezes the exact combined prompt hash',async()=>{
 const f=fixture(true);await f.sendRootWeb('a'.repeat(32));assert.equal(f.requests.length,1);
 const request=f.requests[0];assert.ok(request.prompt.startsWith('Canonical prompt unchanged\n\n'+guidance));
 assert.match(request.prompt,/한 문항은 한 번에 수행할 명확한 회상 또는 판단/);
 assert.match(request.prompt,/generation_id/);assert.match(request.prompt,/Approved scope/);
 const frozen=JSON.parse(f.calls[1].init.body);assert.equal(frozen.promptVersion,'1.82');assert.equal(frozen.promptHash,crypto.createHash('sha256').update(request.prompt).digest('hex'));
 assert.equal(request.autoSend,true);assert.equal(request.files[0].id,'S1');
});
test('a recorded dispatch cannot send another model request',async()=>{
 const f=fixture(false);await assert.rejects(f.sendRootWeb('b'.repeat(32)),/이미 기록/);assert.equal(f.requests.length,0);
});
