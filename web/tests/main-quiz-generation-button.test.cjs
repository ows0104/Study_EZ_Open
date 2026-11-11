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
test('one button requests the newest pipeline (새 구조 2, map-tree/3), opened to students, and says what it approves',async()=>{
  const f=fixture();assert.equal(f.button(f.render()).props.disabled,true);await tick();
  const tree=f.render();const b=f.button(tree);assert.equal(b.props.children,'Main Quiz 만들기');assert.equal(b.props.disabled,false);
  assert.equal(f.nodes(tree,'button').length,1);
  const inputs=f.nodes(tree,'input');assert.equal(inputs.length,1);assert.equal(inputs[0].props.type,'checkbox');assert.equal(inputs[0].props.checked,false);
  assert.equal(f.nodes(tree,'textarea').length,0);assert.equal(f.nodes(tree,'details').length,0);
  const note=JSON.stringify(f.nodes(tree,'div').find(n=>n.props.role==='note'));
  assert.match(note,/이 강의의 승인/);assert.match(note,/OpenAI Codex CLI/);assert.match(note,/새 구조 2/);assert.match(note,/학생에게 바로 공개/);assert.match(note,/빈 목표 추가 최대 2/);assert.match(note,/의학 검토 1/);
  b.props.onClick();b.props.onClick();await tick();
  const writes=f.calls.filter(c=>c.init);assert.equal(writes.length,1);
  const payload=JSON.parse(writes[0].init.body);
  assert.deepEqual({...payload,requestId:undefined},{conceptMap:'',points:'',scope:'',examDate:null,inputMode:'source',authoring:'cli',parallelAuthoring:false,pipeline:'map-tree/3',privatePilot:false,resume:false,requestId:undefined});
  assert.equal(typeof payload.requestId,'string');assert.deepEqual(f.sent,[]);
  assert.equal(f.button(f.render()).props.disabled,true);
});
test('the one checkbox makes the request private to the requester and says so',async()=>{
  const f=fixture();f.render();await tick();
  f.nodes(f.render(),'input')[0].props.onChange({target:{checked:true}});
  const tree=f.render();assert.equal(f.nodes(tree,'input')[0].props.checked,true);
  const note=JSON.stringify(f.nodes(tree,'div').find(n=>n.props.role==='note'));assert.match(note,/내 계정에만 공개/);assert.doesNotMatch(note,/학생에게 바로 공개/);
  f.button(tree).props.onClick();await tick();
  const payload=JSON.parse(f.calls.find(c=>c.init).init.body);assert.equal(payload.privatePilot,true);assert.equal(payload.pipeline,'map-tree/3');
});
test('a new request after an older private, supplied-map, parallel version is the newest default, public',async()=>{
  const f=fixture({id:'published',state:'done',published:true,authoring:'web',privatePilot:true,parallelAuthoring:true,input:{conceptMap:'Existing map',points:'Existing points',scope:'old scope',examDate:'2026-12-01',inputMode:'provided'}},{compatible:false});
  f.render();await tick();const tree=f.render();assert.equal(f.nodes(tree,'input')[0].props.checked,false);
  f.button(tree).props.onClick();await tick();
  const payload=JSON.parse(f.calls.find(c=>c.init).init.body);
  assert.equal(payload.pipeline,'map-tree/3');assert.equal(payload.inputMode,'source');assert.equal(payload.conceptMap,'');assert.equal(payload.scope,'');assert.equal(payload.examDate,null);
  assert.equal(payload.authoring,'cli');assert.equal(payload.parallelAuthoring,false);assert.equal(payload.privatePilot,false);assert.deepEqual(f.sent,[]);
});
test('failed generation resumes its request, authoring and budget without another web dispatch',async()=>{
  const f=fixture({id:'old',requestId:'original',state:'failed',authoring:'web',privatePilot:true,input:{conceptMap:'',points:'',scope:'original scope',examDate:null,inputMode:'source'}});
  f.render();await tick();const tree=f.render();const b=f.button(tree);assert.equal(b.props.children,'Main Quiz 이어서 만들기');
  assert.equal(f.nodes(tree,'input').length,0);assert.match(JSON.stringify(tree),/같은 공개 범위\(.*학생 비공개/);b.props.onClick();await tick();
  const payload=JSON.parse(f.calls.find(c=>c.init).init.body);assert.equal(payload.requestId,'original');assert.equal(payload.resume,true);assert.equal(payload.scope,'original scope');assert.deepEqual(f.sent,[]);
  assert.equal(payload.privatePilot,true);assert.equal(payload.pipeline,undefined);assert.equal(payload.authoring,'web');assert.equal(payload.parallelAuthoring,false);  // the original request, unchanged
});
test('a failed map-tree request resumes only with the administrator reason',async()=>{
  const f=fixture({id:'old',requestId:'mt',state:'failed',authoring:'cli',pipeline:'map-tree/1',parallelAuthoring:false,privatePilot:false,input:{conceptMap:'',points:'',scope:'',examDate:null,inputMode:'source'}});
  f.render();await tick();let tree=f.render();let b=f.button(tree);assert.equal(b.props.children,'Main Quiz 이어서 만들기');assert.equal(b.props.disabled,true);
  const field=f.nodes(tree,'input').find(n=>n.props['aria-label']==='이어 하기 이유');field.props.onChange({target:{value:'runner laptop slept'}});
  tree=f.render();b=f.button(tree);assert.equal(b.props.disabled,false);b.props.onClick();await tick();
  const payload=JSON.parse(f.calls.find(c=>c.init).init.body);
  assert.equal(payload.requestId,'mt');assert.equal(payload.resume,true);assert.equal(payload.pipeline,'map-tree/1');assert.equal(payload.resumeReason,'runner laptop slept');assert.equal(payload.privatePilot,false);
});
test('a failed map-tree/2 request also needs the administrator reason',async()=>{
  const f=fixture({id:'old',requestId:'v3',state:'failed',authoring:'cli',pipeline:'map-tree/2',parallelAuthoring:false,privatePilot:true,input:{conceptMap:'',points:'',scope:'',examDate:null,inputMode:'source'}});
  f.render();await tick();const b=f.button(f.render());assert.equal(b.props.children,'Main Quiz 이어서 만들기');assert.equal(b.props.disabled,true);
});
test('a failed map-tree request can start over: newest default, same scope, fresh request, reason required',async()=>{
  const f=fixture({id:'old',requestId:'mt',state:'failed',authoring:'cli',pipeline:'map-tree/3',parallelAuthoring:false,privatePilot:true,input:{conceptMap:'',points:'',scope:'',examDate:null,inputMode:'source'}});
  f.render();await tick();let tree=f.render();
  let restart=f.nodes(tree,'button').find(b=>b.props.children==='새로 출제 (처음부터)');assert.ok(restart);assert.equal(restart.props.disabled,true);
  assert.equal(f.nodes(tree,'button').length,2);assert.equal(f.nodes(tree,'input').filter(n=>n.props.type==='checkbox').length,0);
  assert.match(JSON.stringify(tree),/수정·추가 횟수를 처음부터/);assert.match(JSON.stringify(tree),/OpenAI Codex CLI/);
  f.nodes(tree,'input').find(n=>n.props['aria-label']==='이어 하기 이유').props.onChange({target:{value:'pipeline changed'}});
  tree=f.render();restart=f.nodes(tree,'button').find(b=>b.props.children==='새로 출제 (처음부터)');assert.equal(restart.props.disabled,false);
  restart.props.onClick();restart.props.onClick();await tick();
  const writes=f.calls.filter(c=>c.init);assert.equal(writes.length,1);
  const payload=JSON.parse(writes[0].init.body);assert.notEqual(payload.requestId,'mt');assert.equal(typeof payload.requestId,'string');
  assert.deepEqual({...payload,requestId:undefined},{conceptMap:'',points:'',scope:'',examDate:null,inputMode:'source',authoring:'cli',parallelAuthoring:false,pipeline:'map-tree/3',privatePilot:true,resume:false,restart:true,resumeReason:'pipeline changed',requestId:undefined});
});
test('a failed request from an older map-tree also offers starting over with the newest pipeline',async()=>{
  const f=fixture({id:'old',requestId:'v1',state:'failed',authoring:'cli',pipeline:'map-tree/1',parallelAuthoring:false,privatePilot:false,input:{conceptMap:'',points:'',scope:'',examDate:null,inputMode:'source'}});
  f.render();await tick();let tree=f.render();
  f.nodes(tree,'input').find(n=>n.props['aria-label']==='이어 하기 이유').props.onChange({target:{value:'x'}});
  f.nodes(f.render(),'button').find(b=>b.props.children==='새로 출제 (처음부터)').props.onClick();await tick();
  const payload=JSON.parse(f.calls.find(c=>c.init).init.body);assert.equal(payload.pipeline,'map-tree/3');assert.equal(payload.privatePilot,false);assert.equal(payload.restart,true);
});
test('no start-over for web or non-map-tree requests, running ones or published ones',async()=>{
  for(const job of [
    {id:'w',requestId:'w',state:'failed',authoring:'web',privatePilot:true,input:{conceptMap:'',points:'',scope:'',examDate:null,inputMode:'source'}},
    {id:'h',requestId:'h',state:'held',authoring:'cli',pipeline:'map-tree/3',privatePilot:false,input:{conceptMap:'',points:'',scope:'',examDate:null,inputMode:'source'}},
    {id:'r',requestId:'r',state:'running',authoring:'cli',pipeline:'map-tree/3',privatePilot:false,input:{conceptMap:'',points:'',scope:'',examDate:null,inputMode:'source'}},
    {id:'p',requestId:'p',state:'done',published:true,authoring:'cli',pipeline:'map-tree/3',privatePilot:false,input:{conceptMap:'',points:'',scope:'',examDate:null,inputMode:'source'}}]){
    const f=fixture(job);f.render();await tick();
    assert.equal(f.nodes(f.render(),'button').some(b=>b.props.children==='새로 출제 (처음부터)'),false,job.id);
  }
});
test('CLI source generation does not require a bridge',async()=>{
  const f=fixture(null,{compatible:false});f.render();await tick();f.button(f.render()).props.onClick();await tick();
  assert.equal(f.calls.filter(c=>c.init).length,1);assert.deepEqual(f.sent,[]);
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
