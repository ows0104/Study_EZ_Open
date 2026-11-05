const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('../node_modules/typescript');
const cache = {};
function load(name) {
  if (cache[name]) return cache[name];
  const source = fs.readFileSync(path.join(__dirname, '../src/connection-pilot', name + '.ts'), 'utf8');
  const code = ts.transpileModule(source, {compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText;
  const exports = {};
  vm.runInNewContext(code, {exports, require: id => load(id.replace('./', ''))});
  cache[name] = exports;
  return exports;
}
const {bundles, REVISION} = load('data');
const {freshSession, reduceSession: reduce, decodeSession, summarize} = load('state');
const id = bundles[0].id;

test('ten uniquely identified draft bundles have distinct prompts and evidence axes', () => {
  assert.equal(bundles.length, 10);
  assert.equal(new Set(bundles.map(b=>b.id)).size, 10);
  for (const b of bundles) {
    for (const k of ['structural','exam','clinical','gap','sources','original','connection','type','role','structure']) assert.ok(b[k]);
    assert.notEqual(b.root.question, b.follow.question);
    assert.ok(b.root.answers.length && b.follow.answers.length);
  }
});
test('follow-up cannot be answered, revealed, or rated before the root is opened', () => {
  let s = freshSession();
  for (const action of [{type:'response',value:'test'},{type:'reveal'},{type:'mark',index:0,value:'recalled'}]) s=reduce(s,{...action,id,step:'follow'});
  assert.equal(s.entries[id].follow.response,'');
  assert.equal(s.entries[id].follow.revealed,false);
  assert.ok(s.entries[id].follow.marks.every(m=>m===''));
});
test('revealing an answer freezes the original response and never sets a recall mark', () => {
  let s = reduce(freshSession(),{type:'response',id,step:'root',value:'M'});
  s=reduce(s,{type:'reveal',id,step:'root'});
  s=reduce(s,{type:'response',id,step:'root',value:'M and N'});
  assert.equal(s.entries[id].root.response,'M');
  assert.equal(summarize(s).recalled,0);
  assert.equal(summarize(s).viewed,0);
});
test('partial list recall stays item-specific and follow-up does not promote root', () => {
  let s=reduce(freshSession(),{type:'reveal',id,step:'root'});
  s=reduce(s,{type:'mark',id,step:'root',index:0,value:'recalled'});
  s=reduce(s,{type:'reveal',id,step:'follow'});
  s=reduce(s,{type:'mark',id,step:'follow',index:0,value:'recalled'});
  assert.equal(s.entries[id].root.marks[1],'');
  assert.equal(summarize(s).recalled,2);
  assert.equal(summarize(s).viewed,1);
});
test('review exposure persists independently of navigation and answer state', () => {
  let s=reduce(freshSession(),{type:'review'});
  s=reduce(s,{type:'select',index:9});
  const restored=decodeSession(JSON.stringify(s));
  assert.equal(restored.reviewSeen,true);
  assert.equal(restored.current,9);
  assert.equal(summarize(restored).viewed,0);
});
test('saved feedback, original answer and item marks survive reload', () => {
  let s=reduce(freshSession(),{type:'response',id,step:'root',value:'수용체'});
  s=reduce(s,{type:'feedback',id,value:'발문 범위가 모호함'});
  s=reduce(s,{type:'reveal',id,step:'root'});
  s=reduce(s,{type:'mark',id,step:'root',index:1,value:'learned'});
  assert.equal(JSON.stringify(decodeSession(JSON.stringify(s))),JSON.stringify(s));
});
test('invalid revisions, malformed marks and impossible stage order are rejected', () => {
  const s=freshSession();
  assert.throws(()=>decodeSession('{bad'));
  assert.throws(()=>decodeSession(JSON.stringify({...s,revision:'old'})));
  assert.throws(()=>decodeSession(JSON.stringify({...s,current:99})));
  s.entries[id].root.marks[0]='recalled';
  assert.throws(()=>decodeSession(JSON.stringify(s)));
  s.entries[id].root.marks[0]='';s.entries[id].follow.revealed=true;
  assert.throws(()=>decodeSession(JSON.stringify(s)));
});
test('invalid navigation and marking cannot create arbitrary entries or scores', () => {
  const s=freshSession();
  assert.equal(reduce(s,{type:'select',index:-1}),s);
  assert.equal(reduce(s,{type:'reveal',id:'unknown',step:'root'}),s);
  const u=reduce(s,{type:'mark',id,step:'root',index:0,value:'recalled'});
  assert.equal(summarize(u).recalled,0);
  assert.equal(u.revision,REVISION);
});
