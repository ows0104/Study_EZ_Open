const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');const path=require('node:path');const vm=require('node:vm');
const ts=require('typescript');const jsx=require('react/jsx-runtime');
const code=ts.transpileModule(fs.readFileSync(path.join(__dirname,'../src/bank/RootGenerationPanel.tsx'),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,jsx:ts.JsxEmit.ReactJSX}}).outputText;
const tick=()=>new Promise(resolve=>setImmediate(resolve));
function fixture(job=null,{compatible=true,loadFails=false}={}){
  let cursor=0;const slots=[],effects=[],calls=[],sent=[],published=[];let loadingFails=loadFails;
  const hooks={
    useState(initial){const i=cursor++;if(!(i in slots))slots[i]=initial;return [slots[i],value=>slots[i]=typeof value==='function'?value(slots[i]):value];},
    useRef(initial){const i=cursor++;return slots[i]??(slots[i]={current:initial});},
    useEffect(fn,deps){const i=cursor++;if(!slots[i]||deps.some((d,k)=>d!==slots[i][k])){slots[i]=deps;effects.push(fn);}}
  };
  const exports={};vm.runInNewContext(code,{exports,setInterval:()=>1,clearInterval(){},crypto:require('node:crypto').webcrypto,require:id=>{
    if(id==='react')return hooks;if(id==='react/jsx-runtime')return jsx;
    if(id==='react-router-dom')return {Link:'a'};if(id.endsWith('.css'))return {};
    if(id==='../bridge/previewBridge')return {extensionCompatible:()=>compatible,extensionInputMinimum:()=>''};
    if(id==='./rootWeb')return {sendRootWeb:async id=>sent.push(id),saveRootWebFile:async()=>{}};
    if(id==='../api')return {api:async(url,init)=>{calls.push({url,init});if(!init){if(loadingFails)throw Error('조회 실패');return {generation:job};}return {generation:{...job,id:'new',state:'held',awaitingWeb:true,published:false}};}};
    throw Error(id);
  }});
  function render(){cursor=0;const child=exports.RootGenerationPanel({subject:'test',runId:'demo',onPublished:()=>published.push(true)});const tree=child.type(child.props);while(effects.length)effects.shift()();return tree;}
  function nodes(tree,type){if(!tree||typeof tree!=='object')return [];if(Array.isArray(tree))return tree.flatMap(x=>nodes(x,type));return [...(tree.type===type?[tree]:[]),...nodes(tree.props?.children,type)];}
  return {render,nodes,calls,sent,published,allowLoad(){loadingFails=false;},button(tree){return nodes(tree,'button')[0];}};
}
test('one click requests source/web generation and automatically dispatches once',async()=>{
  const f=fixture();assert.equal(f.button(f.render()).props.disabled,true);await tick();
  const b=f.button(f.render());assert.equal(b.props.children,'Main Quiz 만들기');assert.equal(b.props.disabled,false);
  b.props.onClick();b.props.onClick();await tick();
  const writes=f.calls.filter(c=>c.init);assert.equal(writes.length,1);
  const payload=JSON.parse(writes[0].init.body);assert.equal(payload.authoring,'web');assert.equal(payload.inputMode,'source');assert.equal(payload.privatePilot,true);assert.equal(payload.resume,false);
  assert.equal(payload.conceptMap,'');assert.equal(payload.points,'');assert.deepEqual(f.sent,['new']);
  assert.equal(f.button(f.render()).props.disabled,true);
});
test('failed generation resumes its request, authoring and budget without another web dispatch',async()=>{
  const f=fixture({id:'old',requestId:'original',state:'failed',authoring:'web',privatePilot:true,input:{conceptMap:'',points:'',scope:'original scope',examDate:null,inputMode:'source'}});
  f.render();await tick();const b=f.button(f.render());assert.equal(b.props.children,'Main Quiz 이어서 만들기');b.props.onClick();await tick();
  const payload=JSON.parse(f.calls.find(c=>c.init).init.body);assert.equal(payload.requestId,'original');assert.equal(payload.resume,true);assert.equal(payload.scope,'original scope');assert.deepEqual(f.sent,[]);
});
test('missing bridge reports an error before creating a job',async()=>{
  const f=fixture(null,{compatible:false});f.render();await tick();f.button(f.render()).props.onClick();await tick();
  assert.equal(f.calls.filter(c=>c.init).length,0);assert.equal(f.nodes(f.render(),'p').some(p=>p.props.role==='alert'),true);
});
test('failed initial lookup can be retried without creating a job',async()=>{
  const f=fixture(null,{loadFails:true});f.render();await tick();let b=f.button(f.render());assert.equal(b.props.children,'기존 작업 다시 확인');assert.equal(b.props.disabled,false);
  f.allowLoad();b.props.onClick();f.render();await tick();b=f.button(f.render());assert.equal(b.props.children,'Main Quiz 만들기');assert.equal(b.props.disabled,false);assert.equal(f.calls.filter(c=>c.init).length,0);
});

test('queued and running jobs block new generation after refresh',async()=>{
  for(const state of ['queued','running']){
    const f=fixture({id:'existing',state,privatePilot:true,input:{conceptMap:'',points:'',scope:'',examDate:null,inputMode:'source'}});
    f.render();await tick();assert.equal(f.button(f.render()).props.disabled,true);assert.equal(f.calls.filter(c=>c.init).length,0);
  }
});
