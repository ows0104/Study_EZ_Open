const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {webcrypto}=require('node:crypto');
const vm=require('node:vm');
global.crypto ??= webcrypto;
require('../../bridge/bank-file.js');
const contract=global.StudyEZBankFile;
const raw=fs.readFileSync(path.join(__dirname,'../fixtures/bank-file-valid.md'),'utf8');
const target={subject:'약리학',runId:'261006_02',promptVersion:'1.76'};
const filename='study-ez-261006_02-bank.md';
const cases=JSON.parse(fs.readFileSync(path.join(__dirname,'../fixtures/bank-file-cases.json'),'utf8'));
test('a real Markdown file checks every format and computes its actual UTF-8 fingerprint',async()=>{
 const bytes=Buffer.from(raw);
 const result=await contract.readFile({name:filename,size:bytes.length,arrayBuffer:async()=>bytes},target);
 assert.equal(result.info.question_count,8);
 assert.equal(result.responseFile.byteLength,bytes.length);
 assert.equal(result.responseFile.sha256,require('node:crypto').createHash('sha256').update(bytes).digest('hex'));
 assert.equal(result.raw,raw);
});
for(const row of cases)test(row.name,()=>{
 assert.notEqual(raw.replace(row.old,row.new),raw);
 assert.throws(()=>contract.inspect(raw.replace(row.old,row.new),target,filename));
});
test('BOM and CRLF preserve source bytes; wrong identity, links and code blocks fail',async()=>{
 const value='\ufeff'+raw.replace(/\n/g,'\r\n');
 const result=await contract.describe(value,target,filename);
 assert.equal(result.raw,value);
 assert.throws(()=>contract.inspect(raw,target,'other.md'));
 assert.throws(()=>contract.inspect('```md\n'+raw+'\n```',target,filename));
 assert.throws(()=>contract.inspect('[bank](sandbox:/mnt/data/'+filename+')',target,filename));
 await assert.rejects(contract.readFile({name:filename,size:99,arrayBuffer:async()=>new Uint8Array([255,254])},target));
});

function collector() {
 const source=fs.readFileSync(path.join(__dirname,'../../bridge/chatgpt-share.js'),'utf8');
 const offered=[]; const requests=[]; const sent=[];
 const ctx=vm.createContext({URL,TextDecoder,Uint8Array,console,StudyEZBankFile:contract,
  location:{href:'https://chatgpt.com/c/demo',pathname:'/c/demo'},
  chrome:{runtime:{id:'test',sendMessage:(m,cb)=>{sent.push(m);cb({ok:true});}}},
  document:{querySelectorAll:()=>[]},
  fetch:async(url,options)=>{requests.push({url,options});return{ok:true,headers:{get:()=>null},arrayBuffer:async()=>Buffer.from(raw)}},
 });
 vm.runInContext(source.slice(0,source.lastIndexOf('void initialize()')),ctx);
 ctx.offered=offered;
 vm.runInContext(`watch={lectureId:'studyez:bank:1.76:약리학/261006_02',mode:'bank',promptVersion:'1.76'}; offerBankFile=message=>offered.push(message);`,ctx);
 return{ctx,offered,requests,sent};
}
test('collector reads an exposed actual file and sends bytes with fingerprint',async()=>{
 const s=collector();
 assert.equal(vm.runInContext('fileMode()',s.ctx),true);
 const result=await vm.runInContext(`collectBankFile('[다운로드](https://chatgpt.com/backend-api/files/${filename})')`,s.ctx);
 assert.equal(result.raw,raw);assert.equal(result.info.question_count,8);
 assert.equal(s.requests.length,1);assert.equal(s.requests[0].options.redirect,'error');
 s.ctx.result=result;
 assert.equal(await vm.runInContext('deliverBankFile(result)',s.ctx),true);
 assert.equal(s.sent[0].responseFile.sha256,result.responseFile.sha256);
 assert.equal(s.sent[0].raw,raw);
});
test('transport lecture prefix resolves to the actual lecture without changing routing identity',()=>{
 const result=contract.lectureTarget('studyez:bank:1.76:약리학/261006_03');
 assert.deepEqual(result,{subject:'약리학',runId:'261006_03',promptVersion:'1.76'});
 assert.deepEqual(contract.lectureTarget('약리학/261006_02','1.76'),target);
});
test('sandbox links offer actual-file selection without guessing download APIs',async()=>{
 const s=collector();
 assert.equal(await vm.runInContext(`collectBankFile('[다운로드](sandbox:/mnt/data/${filename})')`,s.ctx),null);
 assert.equal(s.requests.length,0);assert.equal(s.offered.length,1);
 assert.equal(await vm.runInContext(`collectBankFile('[다운로드](https://evil.example/${filename})')`,s.ctx),null);
 assert.equal(s.requests.length,0);
});
