const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');const path=require('node:path');const vm=require('node:vm');
const ts=require('typescript');
function load(file){
  const js=ts.transpileModule(fs.readFileSync(file,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText;
  const context=vm.createContext({exports:{},require});vm.runInContext(js,context);return context.exports;
}
// Values come from a vm realm; compare their JSON shape, not prototypes.
const same=(a,b,m)=>assert.deepEqual(JSON.parse(JSON.stringify(a)),b,m);
const {buildTree,lanes,lanesPerRow,questionsOf,ancestors,plain}=load(path.join(__dirname,'../src/bank/rootMapTree.ts'));
const direction=id=>({direction_id:id,cue:'cue',answer_scope:'secret',requirement:'required'});
const importance={structural:{status:'insufficient',reason:''},exam:{status:'insufficient',reason:''},clinical:{status:'insufficient',reason:''}};
// Shape of the published 감염병리1 판: topic concepts (two share a title) + one answer node per question.
const published={
  concepts:[{concept_id:'C001',label:'감염·염증의 구별',parent_ids:[]},{concept_id:'C002',label:'감염·염증의 구별',parent_ids:[]},
    {concept_id:'C010',label:'Prion과 CJD',parent_ids:[]},
    ...['N1_A','N2_A','N3_A','N4_A'].map(id=>({concept_id:id,label:'정답 '+id,parent_ids:[]}))],
  relations:['1','2','3','4'].map(i=>({relation_id:`N${i}_R`,from_id:i<'3'?(i==='1'?'C001':'C002'):'C010',to_id:`N${i}_A`,kind:'association',reason:''})),
  targets:[
    {target_id:'N3_T',title:'Prion은 **무엇**인가?',role:'leaf',concept_ids:['C010','N3_A'],directions:[direction('N3_D')],importance,evidence:[{source_id:'S1',pages:[17]}]},
    {target_id:'N1_T',title:'두 요인은?',role:'leaf',concept_ids:['C001','N1_A'],directions:[direction('N1_D')],importance,evidence:[{source_id:'S1',pages:[3]}]},
    {target_id:'N2_T',title:'감염과 염증의 차이는?',role:'leaf',concept_ids:['C002','N2_A'],directions:[direction('N2_D')],importance,evidence:[{source_id:'S1',pages:[4]}]},
    {target_id:'N4_T',title:'보류된 문항',role:'leaf',concept_ids:['C010','N4_A'],directions:[direction('N4_D')],importance,evidence:[{source_id:'S1',pages:[18]}]},
    {target_id:'N5_T',title:'C001 둘째 문항',role:'leaf',concept_ids:['C001'],directions:[direction('N5_D')],importance,evidence:[]}],
  currentConceptIds:['C002','N2_A'],readyDirectionIds:['N1_D','N2_D','N3_D','N5_D'],scope:{label:'',limitations:[]}};
const summary={targets:[{id:'N1_T',learned:true,recalled:true,ready:true},{id:'N2_T',learned:true,recalled:false,ready:true},
  {id:'N3_T',learned:false,recalled:false,ready:true},{id:'N5_T',learned:false,recalled:false,ready:true}]};

test('published shape: lecture → merged topics → questions, answer nodes are not shown',()=>{
  const tree=buildTree(published,summary,'감염성 질환의 병리 1');
  const root=tree.nodes.get(tree.rootId);
  same(root.children.map(id=>tree.nodes.get(id).label),['감염·염증의 구별','Prion과 CJD']);
  const topic=tree.nodes.get(root.children[0]);
  same(topic.conceptIds,['C001','C002']);
  same(topic.children.map(id=>tree.nodes.get(id).targetId),['N1_T','N2_T','N5_T'],'ordered by page, unpaged last');
  assert.equal([...tree.nodes.values()].some(n=>/정답/.test(n.label)),false,'answer nodes never become labels');
  assert.equal(tree.leaves,5);
  assert.equal(tree.currentId,'t:N2_T');same(ancestors(tree,'t:N2_T'),[topic.id,tree.rootId]);
  assert.equal(tree.nodes.get('t:N1_T').status,'is-recalled');assert.equal(tree.nodes.get('t:N2_T').status,'is-learning');
  assert.equal(tree.nodes.get('t:N4_T').status,'is-unready');assert.equal(tree.nodes.get('t:N3_T').label,'Prion은 무엇인가?');
  same({...topic.counts},{'is-new':1,'is-learning':1,'is-recalled':1,'is-unready':0});
  same(topic.pages,[3,4]);assert.equal(topic.current,true);
});

test('explicit parent_ids nest concepts; lanes list every topic top-down with nothing collapsed',()=>{
  const map={concepts:[{concept_id:'A',label:'A',parent_ids:[]},{concept_id:'B',label:'B',parent_ids:['A']},{concept_id:'C',label:'C',parent_ids:['B','A']},{concept_id:'L',label:'Loop',parent_ids:['L']}],
    relations:[],scope:{label:'',limitations:[]},
    targets:[{target_id:'T1',title:'t1',role:'leaf',concept_ids:['A'],directions:[direction('D1')],importance},
      {target_id:'T2',title:'t2',role:'leaf',concept_ids:['C'],directions:[direction('D2')],importance},
      {target_id:'T3',title:'t3',role:'leaf',concept_ids:['L'],directions:[direction('D3')],importance},
      {target_id:'T4',title:'t4',role:'leaf',concept_ids:[],directions:[direction('D4')],importance}]};
  const tree=buildTree(map,{targets:[]},'강의');
  same(ancestors(tree,'t:T2'),['c:C','c:B','c:A','root']);
  assert.equal(tree.nodes.get('t:T4').parent,'c:__other');assert.equal(tree.nodes.get('t:T3').parent,'c:L');
  // One lane per top-level topic; rows are depth-first with depth; questions are not rows.
  same(lanes(tree),[{head:'c:A',rows:[{id:'c:B',depth:1},{id:'c:C',depth:2}]},{head:'c:L',rows:[]},{head:'c:__other',rows:[]}]);
  same(questionsOf(tree,'c:C'),['t:T2']);same(questionsOf(tree,'c:B'),[]);
  const listed=new Set(lanes(tree).flatMap(l=>[l.head,...l.rows.map(r=>r.id)]));
  for(const n of tree.nodes.values())if(n.kind==='concept')assert.ok(listed.has(n.id),`${n.id} is shown without expanding`);
});

test('lane rows stay screen-shaped for flat maps',()=>{
  same([1,7,8,9,16,17,40].map(lanesPerRow),[1,7,8,5,8,6,8]);
});

test('display text drops authored emphasis markers only',()=>{
  assert.equal(plain('**감염**이라고 결론 (O/X) 2*3'),'감염이라고 결론 (O/X) 2*3');
});
