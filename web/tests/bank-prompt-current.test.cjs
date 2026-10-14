const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const ts = require('../node_modules/typescript');
const text = fs.readFileSync(require('node:path').join(__dirname,'../src/bank/prompt.ts'),'utf8');
const code = ts.transpileModule(text,{compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText;
function fixture(response) {
 const exports = {}, calls=[];
 vm.runInNewContext(code,{exports,Date,fetch:async (url,options)=>{calls.push({url,options});return response;},require:id=>{default:id.endsWith('.json')?[]:'<!-- Version: 1.47 -->\nOld {{title}}'}});
 return {...exports,calls};
}
test('a stale loaded tab renders the latest canonical prompt with no cache',async()=>{
 const s=fixture({ok:true,json:async()=>({version:'1.48',template:'<!-- Version: 1.48 -->\nLatest {{title}}\nSTUDYEZ_BANK_COMPLETE'})});
 const result=await s.loadLatestBankPrompt({title:'Lecture'},[]);
 assert.equal(result.version,'1.48');
 assert.equal(result.prompt,'Latest Lecture\nSTUDYEZ_BANK_COMPLETE');
 assert.equal(s.calls[0].options.cache,'no-store');
 assert.match(s.calls[0].url,/^\/bank-prompt.json\?t=/);
});
test('failed or corrupt latest prompt stops instead of falling back to a stale template',async()=>{
 for(const response of [{ok:false},{ok:true,json:async()=>({version:'1.48',template:'<!-- Version: 1.47 --> Old'})}]){
  await assert.rejects(fixture(response).loadLatestBankPrompt({title:'Lecture'},[]));
 }
});
