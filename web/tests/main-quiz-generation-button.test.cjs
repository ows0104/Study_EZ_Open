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
    if(id==='./pollChain')return {pollAfterSettled:()=>()=>{}};
    if(id==='./rootWeb')return {sendRootWeb:async id=>sent.push(id),saveRootWebFile:async()=>{}};
    if(id==='../api')return {api:async(url,init)=>{calls.push({url,init});if(!init){if(loadingFails)throw Error('조회 실패');return {generation:job};}return {generation:{...job,id:'new',state:'queued',awaitingWeb:false,published:false}};}};
    throw Error(id);
  }});
  function render(){cursor=0;const child=exports.RootGenerationPanel({subject:'test',runId:'demo',onPublished:()=>published.push(true)});const tree=child.type(child.props);while(effects.length)effects.shift()();return tree;}
  function nodes(tree,type){if(!tree||typeof tree!=='object')return [];if(Array.isArray(tree))return tree.flatMap(x=>nodes(x,type));return [...(tree.type===type?[tree]:[]),...nodes(tree.props?.children,type)];}
  return {render,nodes,calls,sent,published,allowLoad(){loadingFails=false;},button(tree){return nodes(tree,'button')[0];}};
}
test('one click requests the map-tree pipeline, opened to students, and says what it approves',async()=>{
  const f=fixture();assert.equal(f.button(f.render()).props.disabled,true);await tick();
  const tree=f.render();const b=f.button(tree);assert.equal(b.props.children,'Main Quiz 만들기');assert.equal(b.props.disabled,false);
  const note=JSON.stringify(f.nodes(tree,'div').find(n=>n.props.role==='note'));
  assert.match(note,/이 강의의 승인/);assert.match(note,/OpenAI Codex CLI/);assert.match(note,/학생에게 바로 공개/);assert.match(note,/문항 보완 최대 3/);
  b.props.onClick();b.props.onClick();await tick();
  const writes=f.calls.filter(c=>c.init);assert.equal(writes.length,1);
  const payload=JSON.parse(writes[0].init.body);assert.equal(payload.pipeline,'map-tree/1');assert.equal(payload.authoring,'cli');assert.equal(payload.parallelAuthoring,false);assert.equal(payload.inputMode,'source');assert.equal(payload.privatePilot,false);assert.equal(payload.resume,false);
  assert.equal(payload.conceptMap,'');assert.equal(payload.points,'');assert.deepEqual(f.sent,[]);
  assert.equal(f.button(f.render()).props.disabled,true);
});
test('failed generation resumes its request, authoring and budget without another web dispatch',async()=>{
  const f=fixture({id:'old',requestId:'original',state:'failed',authoring:'web',privatePilot:true,input:{conceptMap:'',points:'',scope:'original scope',examDate:null,inputMode:'source'}});
  f.render();await tick();const b=f.button(f.render());assert.equal(b.props.children,'Main Quiz 이어서 만들기');b.props.onClick();await tick();
  const payload=JSON.parse(f.calls.find(c=>c.init).init.body);assert.equal(payload.requestId,'original');assert.equal(payload.resume,true);assert.equal(payload.scope,'original scope');assert.deepEqual(f.sent,[]);
  assert.equal(payload.pipeline,undefined);assert.equal(payload.authoring,'web');assert.equal(payload.parallelAuthoring,false);  // the original request, unchanged
});
test('a failed map-tree request resumes only with the administrator reason',async()=>{
  const f=fixture({id:'old',requestId:'mt',state:'failed',authoring:'cli',pipeline:'map-tree/1',parallelAuthoring:false,privatePilot:false,input:{conceptMap:'',points:'',scope:'',examDate:null,inputMode:'source'}});
  f.render();await tick();let tree=f.render();let b=f.button(tree);assert.equal(b.props.children,'Main Quiz 이어서 만들기');assert.equal(b.props.disabled,true);
  const field=f.nodes(tree,'input').find(n=>n.props['aria-label']==='이어 하기 이유');field.props.onChange({target:{value:'runner laptop slept'}});
  tree=f.render();b=f.button(tree);assert.equal(b.props.disabled,false);b.props.onClick();await tick();
  const payload=JSON.parse(f.calls.find(c=>c.init).init.body);
  assert.equal(payload.requestId,'mt');assert.equal(payload.resume,true);assert.equal(payload.pipeline,'map-tree/1');assert.equal(payload.resumeReason,'runner laptop slept');assert.equal(payload.privatePilot,false);
});
test('the earlier parallel mode stays selectable',async()=>{
  const f=fixture();f.render();await tick();let tree=f.render();
  const radio=f.nodes(tree,'input').filter(n=>n.props.type==='radio')[1];radio.props.onChange();
  tree=f.render();assert.equal(f.nodes(tree,'div').some(n=>n.props.role==='note'),false);f.button(tree).props.onClick();await tick();
  const payload=JSON.parse(f.calls.find(c=>c.init).init.body);assert.equal(payload.parallelAuthoring,true);assert.equal(payload.pipeline,undefined);
});
test('CLI source generation does not require a bridge',async()=>{
  const f=fixture(null,{compatible:false});f.render();await tick();f.button(f.render()).props.onClick();await tick();
  assert.equal(f.calls.filter(c=>c.init).length,1);assert.deepEqual(f.sent,[]);
});
test('new authoring with a supplied map also stays on CLI without a bridge',async()=>{
  const f=fixture({id:'published',state:'done',published:true,authoring:'web',privatePilot:true,input:{conceptMap:'Existing map',points:'Existing points',scope:'',examDate:null,inputMode:'provided'}},{compatible:false});
  f.render();await tick();f.button(f.render()).props.onClick();await tick();
  const payload=JSON.parse(f.calls.find(c=>c.init).init.body);assert.equal(payload.authoring,'cli');assert.equal(payload.parallelAuthoring,false);assert.deepEqual(f.sent,[]);
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
