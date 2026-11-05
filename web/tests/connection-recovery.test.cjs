const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');
const source = fs.readFileSync(path.join(__dirname, '../src/bank/connectionRecovery.ts'), 'utf8');
const exports_ = {};
vm.runInNewContext(ts.transpileModule(source, {compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText, {exports:exports_});
const { connectionRecovery } = exports_;
function memory() {
  const map = new Map();
  return {get length(){return map.size;}, key:i=>[...map.keys()][i], getItem:k=>map.get(k)??null,
    setItem:(k,v)=>map.set(k,v), removeItem:k=>map.delete(k)};
}
const payload = (id='one') => ({requestId:id,version:0,kind:'reveal',index:0,step:'root',response:'Original'});
test('separate tabs retain separate requests and confirmation removes only its own request', () => {
  const storage=memory(), a=connectionRecovery(storage,'a','test','demo','v1'), b=connectionRecovery(storage,'a','test','demo','v1');
  a.save(payload()); b.save(payload('two')); a.confirm(payload());
  assert.equal(b.read().length,1); assert.equal(b.read()[0].payload.requestId,'two');
  assert.throws(()=>b.save({...payload('two'),response:'changed'}));
  assert.equal(b.read()[0].payload.response,'Original');
});
test('legacy pending and conflict inputs survive migration and account/revision separation', () => {
  const storage=memory(), old='studyez:connection-write:a:test:demo:v1';
  storage.setItem(old,JSON.stringify(payload())); storage.setItem(old+':conflict',JSON.stringify(payload('two')));
  const a=connectionRecovery(storage,'a','test','demo','v1');
  assert.equal(a.read().length,2); assert.equal(storage.getItem(old),null);
  assert.equal(a.read().find(x=>x.payload.requestId==='two').conflict,true);
  assert.equal(connectionRecovery(storage,'b','test','demo','v1').read().length,0);
  assert.equal(connectionRecovery(storage,'a','test','demo','v2').read().length,0);
});
test('drafts persist by question, step and account; malformed requests stay untouched', () => {
  const storage=memory(), a=connectionRecovery(storage,'a','test','demo','v1');
  a.saveDraft('b1','root','My draft');
  assert.equal(connectionRecovery(storage,'a','test','demo','v1').draft('b1','root'),'My draft');
  assert.equal(a.draft('b1','follow'),''); assert.equal(a.draft('b2','root'),'');
  assert.equal(connectionRecovery(storage,'b','test','demo','v1').draft('b1','root'),'');
  const old='studyez:connection-write:a:test:demo:v1';storage.setItem(old,'{broken');
  assert.throws(()=>a.read()); assert.equal(storage.getItem(old),'{broken');
});
