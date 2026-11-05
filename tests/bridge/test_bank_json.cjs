const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
global.crypto ??= require('node:crypto').webcrypto;
require('../../bridge/bank-file.js');
const c=global.StudyEZBankFile;
const raw=fs.readFileSync(path.join(__dirname,'../fixtures/bank-file-valid.json'),'utf8');
const target={subject:'약리학',runId:'261006_02',promptVersion:'1.80'};
const name=c.filenameFor(target);
test('pure JSON checks all six formats and preserves actual bytes',async()=>{
 const value='\ufeff'+raw.replace(/\n/g,'\r\n');
 const result=await c.describe(value,target,name);
 assert.equal(result.raw,value);assert.equal(result.info.question_count,6);
 assert.equal(result.responseFile.sha256,require('node:crypto').createHash('sha256').update(value).digest('hex'));
 assert.equal(c.metadata(value).generation_id,'ab682837b3c34916a2c0c77c342bd115');
 assert.equal(name,'study-ez-261006_02-bank.json');
 assert.throws(()=>c.inspect(raw,{...target,promptVersion:'1.81'},name));
 assert.throws(()=>c.inspect(raw,{...target,subject:'other'},name));
});
const broken=[
 [['complete'],false],[['schema_version'],true],[['question_count'],5],
 [['question_ids'],['Q001']],[['questions',0,'question_id'],'Q002'],
 [['questions',0,'importance'],4],[['questions',0,'advanced'],'false'],
 [['questions',0,'unexpected'],'value'],[['questions',0,'answers'],[]],
 [['questions',1,'question'],'Bad {{A}}'],[['questions',1,'answers'],['A']],
 [['questions',3,'explanation'],''],[['questions',3,'conflict_id'],'CF999'],
 [['questions',4,'answers'],['Z']],[['questions',4,'mcq_mode'],'none'],
 [['questions',4,'options',1,'id'],'A'],[['questions',0,'evidence','slides'],[]],
 [['questions',0,'evidence','slides',0,'page'],true],[['conflict_ids'],[]],
 [['source_conflicts',0,'unresolved'],'false'],[['prompt_version'],'1.79']
];
for(const [keys,value] of broken)test('rejects broken JSON '+keys.join('.'),()=>{
 const doc=JSON.parse(raw);let cursor=doc;for(const key of keys.slice(0,-1))cursor=cursor[key];cursor[keys.at(-1)]=value;
 assert.throws(()=>c.inspect(JSON.stringify(doc),target,name));
});
test('rejects duplicate keys, nonfinite numbers, markdown and trailing markers',()=>{
 for(const bad of [raw+'\nSTUDYEZ_BANK_COMPLETE','```json\n'+raw+'\n```',raw.replace('"complete": true','"complete": true,"complete": true'),raw.replace('"importance":5','"importance":1e999')])assert.throws(()=>c.inspect(bad,target,name));
 const legacy=fs.readFileSync(path.join(__dirname,'../fixtures/bank-file-valid.md'),'utf8');
 assert.equal(c.inspect(legacy,{...target,promptVersion:'1.76'},name.replace('.json','.md')).question_count,8);
 assert.throws(()=>c.inspect(legacy.replaceAll('1.76','1.80'),target,name.replace('.json','.md')));
});
