const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');
const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');
function load(file) {
  const code = ts.transpileModule(fs.readFileSync(file,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,jsx:ts.JsxEmit.ReactJSX}}).outputText;
  const ctx=vm.createContext({exports:{},require:name=> {
    if(name.endsWith('/SlideImage')) return {SlideImage:({src,alt})=>React.createElement('img',{src,alt})};
    if(name.endsWith('.css')) return {};
    if(name.startsWith('.')) {const target=path.resolve(path.dirname(file),name); return load(target+(fs.existsSync(target+'.tsx')?'.tsx':'.ts'));}
    return require(name);
  }});
  vm.runInContext(code,ctx); return ctx.exports;
}
const {AnswerBody}=load(path.join(__dirname,'../src/bank/BankQuestion.tsx'));
const q={question_id:'q1',question:'A?',format:'basic',options:[],matching_left:[],matching_right:[]};
const a={answer:'B',answerUnits:['B'],answerPairs:[],correctOrder:[],correctOptionIds:[],medicalReview:null,slides:[{page:1,url:'https://example.test/background.png'}]};
const image=(page,primary)=>({page,primary,url:`https://example.test/${page}.png`,pdfFilename:'족보.pdf',references:[`2022 ${page}번`]});
const render=answer=>renderToStaticMarkup(React.createElement(AnswerBody,{question:q,answer:{...a,...answer}}));
test('reference exams open beside selected lecture evidence with year and question labels',()=>{
  const html=render({slides:[{page:8,primary:true,url:'https://example.test/core.png'}],
    jokboSlides:[{...image(12,false),references:['2023 52번','2022년 7번']}],
    evidenceStatus:{category:'partial_support',reason:'일부 확인'}});
  assert.match(html,/class="bank-evidence-pair"/);
  assert.match(html,/src="https:\/\/example.test\/core.png"/);
  assert.match(html,/src="https:\/\/example.test\/12.png"/);
  assert.match(html,/<figcaption class="bank-note">2023년 · 52번 · 2022년 · 7번<\/figcaption>/);
  assert.doesNotMatch(html,/<h2>참고한 족보|족보\.pdf|지면 크게 보기|bank-jokbo-reference/);
  assert.doesNotMatch(html,/<details/);
  assert.doesNotMatch(html,/핵심 근거 · 족보/);
});

test('a selected exam page is the core; other exam references stay closed and unloaded',()=>{
  const html=render({jokboSlides:[image(2,false),image(9,true)],evidenceStatus:{category:'exam_only',reason:'족보에만 있음',primaryAvailable:true}});
  assert.match(html,/핵심 근거 · 족보/); assert.match(html,/src="https:\/\/example.test\/9.png"/);
  assert.doesNotMatch(html,/src="https:\/\/example.test\/2.png"/);
  assert.match(html,/추가 참고 족보 1장/); assert.match(html,/추가 참고 슬라이드 1장/);
  assert.doesNotMatch(html,/확인된 핵심 근거 슬라이드가 없습니다/);
  assert.ok(html.indexOf('핵심 근거 · 족보')<html.indexOf('추가 참고 슬라이드'));
});
test('each unresolved cause stays visible with its concrete missing claim and no core claim',()=>{
  for(const [category,title] of Object.entries({partial_support:'근거 일부 부족',source_conflict:'자료 충돌',unsupported:'근거 미확인',uncertain:'근거 판정 어려움'})) {
    const html=render({jokboSlides:[image(4,false)],evidenceStatus:{category,reason:'실제 자료의 차이',missingClaim:'확인할 핵심'}});
    assert.match(html,new RegExp(title)); assert.match(html,/실제 자료의 차이/); assert.match(html,/확인할 핵심/);
    assert.doesNotMatch(html,/핵심 근거 · 족보/);
    assert.match(html,/참고 족보 1장/); assert.doesNotMatch(html,/src="https:\/\/example.test\/4.png"/);
  }
});
test('exam captions stay compact; absent selected images are explicit; legacy references still render',()=>{
  const embedded=render({jokboSlides:[{...image(37,true),embedded:true}]});
  assert.match(embedded,/<figcaption class="bank-note">2022년 · 37번<\/figcaption>/);
  assert.doesNotMatch(embedded,/필기 PDF에 첨부된 기출|족보\.pdf|지면 크게 보기/);
  assert.match(render({evidenceStatus:{category:'exam_only',reason:'확인',primaryAvailable:false}}),/핵심 족보 지면을 아직 표시할 수 없습니다/);
  const html=render({jokboSlides:[image(3,false)]}); assert.match(html,/참고한 족보/); assert.match(html,/3.png/);
});
