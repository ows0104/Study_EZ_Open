const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');const path=require('node:path');const vm=require('node:vm');
const ts=require('typescript');const React=require('react');const {renderToStaticMarkup}=require('react-dom/server');
function load(file){
  const js=ts.transpileModule(fs.readFileSync(file,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX}}).outputText;
  const context=vm.createContext({exports:{},require:name=>{
    if(name.endsWith('.css'))return {};
    if(!name.startsWith('.'))return require(name);
    const target=path.resolve(path.dirname(file),name);
    return load(fs.existsSync(target+'.tsx')?target+'.tsx':target+'.ts');
  }});vm.runInContext(js,context);return context.exports;
}
const {RootSolve}=load(path.join(__dirname,'../src/bank/RootSolve.tsx'));
const question={question_id:'Q1',format:'mcq',question:'판별할 병원체는?',options:[{id:'A',text:'선지 비밀 A'},{id:'B',text:'선지 비밀 B'}],sequence_items:[],matching_items:[],mcq_mode:'recall_first'};
function render(change={}){
 const task={id:'task1',question,answer:null,response:null,attempted:null,helped:false,...change};
 return renderToStaticMarkup(React.createElement(RootSolve,{view:{revision:'v1',position:0,count:1,task,blocked:null,finished:false,canUndo:false,mapSeen:false},scope:'synthetic',disabled:false,advancing:false,onAction:()=>{},onToday:()=>{},onError:()=>{}}));
}
test('recall first hides answers and choices without a response textbox',()=>{
 const html=render();assert.doesNotMatch(html,/선지 비밀|Secret answer/);assert.match(html,/선지 보기/);assert.doesNotMatch(html,/<textarea|내 답 적기/);
 assert.doesNotMatch(html,/Again|Hard|Good|Easy/);
});
test('comparison displays choices as the task without leaking the answer',()=>{
 const html=render({question:{...question,mcq_mode:'comparison'}});
 assert.match(html,/선지 비밀 A/);assert.doesNotMatch(html,/선지 보기|Secret answer/);
});
test('all four self-ratings remain selectable even after help or answer-only',()=>{
 const answer={answer:'Secret answer',answerUnits:[],correctOptionIds:['A'],answerPairs:[],correctOrder:[],slides:[],explanation:'',sourceRefs:[],reviewNotes:[]};
 const html=render({answer,attempted:true,helped:true});
 assert.match(html,/Secret answer/);
 for(const rating of ['Again','Hard','Good','Easy'])assert.match(html,new RegExp(rating+'<kbd>'));
 for(const value of [html,render({answer,attempted:false}),render({answer,attempted:true})]){
   assert.doesNotMatch(value,/<button[^>]*disabled[^>]*><span class="quiz-grade-name">/);
 }
});
