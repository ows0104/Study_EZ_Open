const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');
const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');
function load(file) {
  const code = ts.transpileModule(fs.readFileSync(file,'utf8'),{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.CommonJS,jsx:ts.JsxEmit.ReactJSX}}).outputText;
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
test('exam questions and options are visible while original PDF pages stay closed',()=>{
  const question={reference:'2023 52번',stem:'원문 문제는 무엇인가?',options:['① 첫 선지','② 둘째 선지'],needsFigure:true};
  const html=render({slides:[{page:8,primary:true,url:'https://example.test/core.png'}],
    jokboSlides:[{...image(12,false),questions:[question]},{...image(13,false),questions:[question]}]});
  assert.match(html,/참고 족보 문제/);
  assert.equal(html.split('원문 문제는 무엇인가?').length-1,1);
  assert.match(html,/① 첫 선지/); assert.match(html,/② 둘째 선지/);
  assert.match(html,/그림·표는 아래 원본 PDF에서 확인/);
  assert.match(html,/원본 PDF 펼쳐보기 · 족보.pdf · 12쪽/);
  assert.doesNotMatch(html,/src="https:\/\/example.test\/12.png"/);
  assert.match(html,/src="https:\/\/example.test\/core.png"/);
});

test('primary exam labels and unresolved evidence status are preserved',()=>{
  const html=render({jokboSlides:[image(2,false),image(9,true)],evidenceStatus:{category:'exam_only',reason:'족보에만 있음',primaryAvailable:true}});
  assert.match(html,/핵심 근거 · 족보/);
  assert.match(html,/원본 PDF 펼쳐보기/);
  assert.doesNotMatch(html,/src="https:\/\/example.test\/9.png"/);
  for(const [category,title] of Object.entries({partial_support:'근거 일부 부족',source_conflict:'자료 충돌',unsupported:'근거 미확인',uncertain:'근거 판정 어려움'})) {
    const unresolved=render({jokboSlides:[image(4,false)],evidenceStatus:{category,reason:'실제 자료의 차이',missingClaim:'확인할 핵심'}});
    assert.match(unresolved,new RegExp(title)); assert.match(unresolved,/확인할 핵심/);
    assert.match(unresolved,/원본 PDF 펼쳐보기/);
  }
});

test('legacy pages remain available with an explicit missing-text message',()=>{
  const html=render({jokboSlides:[image(3,false)]});
  assert.match(html,/문제 본문이 아직 연결되지 않았습니다/);
  assert.match(html,/2022년 · 3번/);
  assert.match(html,/원본 PDF 펼쳐보기 · 족보.pdf · 3쪽/);
});

test('exam answers preserve source objections and explicitly flag missing answers',()=>{
  const question={reference:'2023 52번',stem:'정답 확인 문항',options:['① A','② B'],answer:'2'};
  const show=extra=>render({jokboSlides:[{...image(12,false),questions:[{...question,...extra}]}]});
  assert.match(show({}),/족보 정답: <\/strong>2/);
  assert.match(show({}),/원본 정답표 기준/);
  assert.doesNotMatch(show({}),/정답 의심/);
  assert.match(show({objection:'복수 정답 가능'}),/정답 의심 · 원본 이의제기: 복수 정답 가능/);
  assert.match(show({answer:null}),/미확인/);
  assert.match(show({answer:'  '}),/확인 필요 · 저장된 족보 정답이 없습니다/);
  assert.match(show({answer:undefined}),/확인 필요/);
  assert.match(show({answer:null,objection:'원문 누락'}),/정답 의심 · 원본 이의제기: 원문 누락/);
});

test('medical review distinguishes suggested answers, original errors, uncertainty and unresolved questions',()=>{
  const question={reference:'2023 52번',stem:'검수 문항',options:['① A','② B'],answer:'1'};
  const review={answer:'2',answerText:'B',status:'corrected',confidence:'high',reason:'첫 선지의 작용 방향이 반대입니다.',
    sources:[{kind:'external',locator:'공식 허가사항',url:'https://example.test/label',support:'수용체 차단 작용'}]};
  const show=extra=>render({jokboSlides:[{...image(12,false),questions:[{...question,answerReview:{...review,...extra}}]}]});
  assert.match(show({}),/검토 정답: <\/strong>2 · B/);
  assert.match(show({}),/원본 정답표: 1/);
  assert.match(show({}),/원본 정답 오류 · 첫 선지의 작용 방향이 반대입니다/);
  assert.match(show({}),/정답 검수 근거/);
  assert.match(show({}),/href="https:\/\/example.test\/label"/);
  assert.doesNotMatch(show({}),/별도 검수 전/);
  assert.match(show({status:'doubt',confidence:'medium',reason:'발문 조건에 따라 1번도 가능합니다.'}),/추정 정답/);
  assert.match(show({status:'doubt',confidence:'medium',reason:'발문 조건에 따라 1번도 가능합니다.'}),/정답 의심 · 발문 조건에 따라 1번도 가능합니다/);
  assert.match(show({status:'unresolved',answer:'',answerText:'',confidence:'low',reason:'그래프 축이 판독되지 않습니다.'}),/족보 정답: <\/strong>1/);
  assert.match(show({status:'unresolved',answer:'',answerText:'',confidence:'low',reason:'그래프 축이 판독되지 않습니다.'}),/확인 필요 · 그래프 축이 판독되지 않습니다/);
  const verified=show({status:'verified',answer:'1',answerText:'A',reason:'강의자료와 기전이 일치합니다.'});
  assert.match(verified,/강의자료와 기전이 일치합니다/);
  assert.doesNotMatch(verified,/정답 의심|원본 정답 오류|원본 정답표: 1/);
  const unsafe=show({sources:[{kind:'external',locator:'안전하지 않은 주소',url:'javascript:alert(1)',support:'근거'}]});
  assert.doesNotMatch(unsafe,/href="javascript:/);
});
