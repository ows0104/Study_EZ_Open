// Main-Quiz 근거 배치(2026-11-08): 핵심 슬라이드만 펼치고 나머지는 접는다, 족보는 연도·번호와 함께.
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');const path=require('node:path');const vm=require('node:vm');
const ts=require('typescript');const React=require('react');const {renderToStaticMarkup}=require('react-dom/server');
const stubs={'pdfjs-dist':{GlobalWorkerOptions:{},PDFDataRangeTransport:class{},getDocument:()=>{throw new Error('not in SSR');}},
  'pdfjs-dist/build/pdf.worker.min.mjs?url':''};
function load(file){
  // Vite가 채우는 import.meta.env는 CommonJS 검사에서 고정값으로 둔다.
  const source=fs.readFileSync(file,'utf8').replace(/import\.meta\.env\.BASE_URL/g,'"/"').replace(/import\.meta\.env\.\w+/g,'undefined');
  const js=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX}}).outputText;
  const context=vm.createContext({exports:{},require:name=>{
    if(name in stubs)return name.endsWith('?url')?{default:''}:stubs[name];
    if(name.endsWith('.css'))return {};
    if(name==='../api')return {apiUrl:p=>p,authHeader:async()=>({})};
    if(!name.startsWith('.'))return require(name);
    const target=path.resolve(path.dirname(file),name);
    return load(fs.existsSync(target+'.tsx')?target+'.tsx':target+'.ts');
  }});vm.runInContext(js,context);return context.exports;
}
const {RootPdfSlides,RootJokboSlides}=load(path.join(__dirname,'../src/bank/RootPdfSlides.tsx'));
const slide=(page,extra={})=>({sourceId:'S1',sourceSha256:'a'.repeat(64),sourceFilename:'notes.pdf',page,url:'https://x.invalid/s.pdf',proxyPath:'/p',...extra});
const html=(el,props)=>renderToStaticMarkup(React.createElement(el,props));
const open=markup=>[...markup.split(/<details/)[0].matchAll(/PDF (\d+)쪽/g)].map(m=>Number(m[1]));

test('reviewed focus opens only core slides and folds the rest',()=>{
  const out=html(RootPdfSlides,{slides:[slide(3,{primary:true}),slide(2),slide(5)],focusKnown:true});
  assert.deepEqual(open(out),[3]);assert.match(out,/추가 참고 슬라이드 2장/);
});
test('reviewed focus without a core says so unless an evidence status explains it',()=>{
  assert.match(html(RootPdfSlides,{slides:[slide(2)],focusKnown:true}),/확인된 핵심 근거 슬라이드가 없습니다/);
  assert.doesNotMatch(html(RootPdfSlides,{slides:[slide(2)],focusKnown:true,statusKnown:true}),/확인된 핵심 근거/);
});
test('without reviewed evidence the first cited slide stays open as before',()=>{
  const out=html(RootPdfSlides,{slides:[slide(2),slide(3)]});
  assert.deepEqual(open(out),[2]);assert.match(out,/추가 참고 슬라이드 1장/);assert.doesNotMatch(out,/확인된 핵심/);
});
test('exam pages carry year and number; a core exam page is titled as core evidence',()=>{
  const exam=(page,refs,primary=false)=>slide(page,{sourceId:'S2',sourceFilename:'족보.pdf',references:refs,primary});
  const core=html(RootJokboSlides,{slides:[exam(3,['2021 16번'],true),exam(7,['2023 79번'])]});
  assert.match(core,/핵심 근거 · 족보/);assert.match(core,/2021년 · 16번 · PDF 3쪽/);assert.match(core,/추가 족보 지면 1장/);
  const ref=html(RootJokboSlides,{slides:[exam(7,['2023 79번'])]});
  assert.match(ref,/참고 족보 문제/);assert.match(ref,/2023년 · 79번 · PDF 7쪽/);assert.doesNotMatch(ref,/핵심 근거/);
});
