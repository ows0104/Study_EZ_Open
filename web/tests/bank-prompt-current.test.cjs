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

test('a loaded tab uses fresh lecture scopes together with the latest template',async()=>{
 const scope={title:'CNS lecture',sourcePrefix:'[261006_02]',instruction:'Current source-color scope'};
 const s=fixture({ok:true,json:async()=>({version:'1.75',template:'<!-- Version: 1.75 -->\n{{lecture_scope}}\n\n{{title}}\nSTUDYEZ_BANK_COMPLETE',lectureScopes:[scope]})});
 const source={id:'S1',kind:'notes_current',filename:'[261006_02] notes.pdf'};
 const result=await s.loadLatestBankPrompt({title:scope.title},[source]);
 assert.ok(result.prompt.includes(scope.instruction));
 assert.ok(!(await s.loadLatestBankPrompt({title:'Other lecture'},[source])).prompt.includes(scope.instruction));
 assert.ok(!(await s.loadLatestBankPrompt({title:scope.title},[{...source,filename:'[261006_03] notes.pdf'}])).prompt.includes(scope.instruction));
});

test('invalid fresh lecture scopes stop transmission instead of silently dropping scope',async()=>{
 for(const lectureScopes of [null,{},[null],[{}],[{title:'CNS',sourcePrefix:'[261006_02]',instruction:''}]]) {
  const s=fixture({ok:true,json:async()=>({version:'1.75',template:'<!-- Version: 1.75 -->\nSTUDYEZ_BANK_COMPLETE',lectureScopes})});
  await assert.rejects(s.loadLatestBankPrompt({title:'CNS'},[]),/출제 범위/);
 }
});

test('canonical web prompt includes the exact matching lecture scope and keeps other lectures separate',()=>{
 const path=require('node:path');
 const template=fs.readFileSync(path.join(__dirname,'../../content/prompts/bank/bankPrompt.md'),'utf8');
 const scopes=JSON.parse(fs.readFileSync(path.join(__dirname,'../../content/prompts/bank/lectureScopes.json'),'utf8'));
 const exports={};
 vm.runInNewContext(code,{exports,require:id=>({default:id.endsWith('.json')?scopes:
  id.includes('fileDelivery')?fs.readFileSync(path.join(__dirname,'../../content/prompts/bank/fileDelivery.md'),'utf8'):
  id.includes('textDelivery')?fs.readFileSync(path.join(__dirname,'../../content/prompts/bank/textDelivery.md'),'utf8'):template})});
 for(const scope of scopes) {
 const source={kind:'notes_current',filename:scope.sourcePrefix+' lecture.pdf',id:'S1'};
 assert.ok(exports.renderBankPrompt({title:scope.title},[source]).includes(scope.instruction));
 const other=exports.renderBankPrompt({title:'Other lecture'},[source]);
 assert.ok(!other.includes(scope.instruction));
 assert.ok(!other.includes('별도 지정 없음'));
 assert.ok(!other.includes('{{lecture_scope}}'));
 assert.match(other,/강의: Other lecture\n\n## 1\./);
 const wrongSource=exports.renderBankPrompt({title:scope.title},[{...source,filename:'different.pdf'}]);
 assert.ok(!wrongSource.includes(scope.instruction));
 assert.ok(!wrongSource.includes('별도 지정 없음'));
 const current=exports.renderBankPrompt({title:scope.title},[source]);
 assert.ok(!/\{\{(?:delivery_instructions|run_id|prompt_version|subject)\}\}/.test(current));
 assert.ok(current.includes('schema_version: 2'));
 assert.ok(current.includes(`study-ez-${scope.sourcePrefix.slice(1,-1)}-bank.json`));
 }
});

test('all lectures receive file delivery with their own identity, including non-pharmacology',()=>{
 const path=require('node:path'); const exports={};
 const template=fs.readFileSync(path.join(__dirname,'../../content/prompts/bank/bankPrompt.md'),'utf8');
 const file=fs.readFileSync(path.join(__dirname,'../../content/prompts/bank/fileDelivery.md'),'utf8');
 vm.runInNewContext(code,{exports,require:id=>({default:id.endsWith('.json')?[]:id.includes('fileDelivery')?file:template})});
 for(const [subject,runId,title] of [['약리학','261012_02','항생제 치료의 기본 원리(윤성혜)'],['병리학','261019_01','병리학 강의']]) {
  const prompt=exports.renderBankPrompt({subject,runId,title},[{id:'S1',kind:'notes_current',filename:`[${runId}] notes.pdf`}]);
  assert.ok(prompt.includes(`study-ez-${runId}-bank.json`));
  assert.ok(prompt.includes(`subject는 "${subject}"`));
  assert.ok(prompt.includes('schema_version: 2'));
  assert.ok(!prompt.includes('파일 링크로 본문을 대신하지 않는다'));
  assert.ok(!/\{\{(?:run_id|subject|prompt_version|delivery_instructions)\}\}/.test(prompt));
 }
});

test('professor preparation uses explicit notes groups and never the note writer',()=>{
 const s=fixture({ok:false});
 const source=filename=>[{kind:'notes_current',filename}];
 assert.match(s.professorInformation(source('[261007_01] 강의 (조정현)_황다현v1.pdf')),/조정현/);
 assert.match(s.professorInformation(source('[261105_07] 심내막염, 중추신경계감염_서윤성v1.pdf')),/미확인/);
 assert.ok(!s.professorInformation(source('[261105_07] 강의_서윤성v1.pdf')).includes('서윤성'));
});
