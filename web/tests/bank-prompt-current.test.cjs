const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const ts = require('../node_modules/typescript');
const text = fs.readFileSync(require('node:path').join(__dirname,'../src/bank/prompt.ts'),'utf8');
const code = ts.transpileModule(text,{compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText;
function fixture(response) {
 const exports = {}, calls=[];
 vm.runInNewContext(code,{exports,Date,fetch:async (url,options)=>{calls.push({url,options});return response;},require:id=>({default:id.endsWith('.json')?[]:'<!-- Version: 1.47 -->\nOld {{title}}'})});
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

test('canonical web prompt includes the exact matching lecture scope and keeps other lectures separate',()=>{
 const path=require('node:path');
 const template=fs.readFileSync(path.join(__dirname,'../src/bank/bankPrompt.md'),'utf8');
 const scopes=JSON.parse(fs.readFileSync(path.join(__dirname,'../src/bank/lectureScopes.json'),'utf8'));
 const exports={};
 vm.runInNewContext(code,{exports,require:id=>({default:id.endsWith('.json')?scopes:template})});
 const scope=scopes[0];
 const source={kind:'notes_current',filename:scope.sourcePrefix+' lecture.pdf',id:'S1'};
 assert.ok(exports.renderBankPrompt({title:scope.title},[source]).includes(scope.instruction));
 const other=exports.renderBankPrompt({title:'Other lecture'},[source]);
 assert.ok(!other.includes(scope.instruction));
 assert.ok(other.includes('별도 지정 없음'));
 const wrongSource=exports.renderBankPrompt({title:scope.title},[{...source,filename:'different.pdf'}]);
 assert.ok(!wrongSource.includes(scope.instruction));
});
