const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('../node_modules/typescript');
function load(name) {
  const exports = {};
  const code = ts.transpileModule(fs.readFileSync(path.join(__dirname, '../src/lecture', name+'.ts'), 'utf8'),
    {compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText;
  vm.runInNewContext(code, {exports, require:id=>load(id.replace('./',''))});
  return exports;
}
const p = load('reviewProfessor');
test('read the actual professor without treating the writer or numeric sequence as a professor', () => {
  for (const [filename, names] of [
    ['[261001_01]약물대사(1)(허기영)_김필기 v2.pdf',['허기영']],
    ['[261001_01]약물대사(문경철김혜령)_김필기v2.pdf',['문경철','김혜령']],
    ['[261001_01]약물대사(송현범, 김주현)_필기자.pdf',['송현범','김주현']],
    ['[261001_01]약물대사(2)_김필기.pdf',[]],
    ['[261001_01]약물대사_PK_김필기(허기영).pdf',[]],
  ]) assert.deepEqual(Array.from(p.professorsFromNotesFilename(filename)), names);
});
test('a changed professor overrides timetable tokens for review while preview stays on the timetable', () => {
  const detail = {title:'약물대사',professors:['유경상'],date:'2026-11-01',subject:'약리학',files:[
    {kind:'notes_current',filename:'[261001_01]약물대사(허기영)_김필기.pdf'},
    {kind:'notes_prev',filename:'[251001_01]약물대사(유경상)_이필기.pdf'},
  ]};
  const review = load('reviewPrompt').renderReviewPrompt('{교수}\n{파일명}',detail);
  assert.ok(review.startsWith('허기영\n[261001_01]'));
  assert.equal(review, '허기영\n[261001_01]약물대사(허기영)_김필기.pdf\n\n올해 담당 교수: 허기영');
  const preview = load('previewPrompt').renderPreviewPrompt('{교수}\n{파일명}',detail);
  assert.ok(preview.startsWith('유경상\n[251001_01]'));
  assert.ok(!preview.includes('복습 담당 교수 확인'));
});
test('custom review templates receive one professor line and unknowns are not replaced by timetable guesses', () => {
  const detail = {title:'강의',professors:['예정교수'],date:'2026-11-01',subject:'과목',files:[
    {kind:'notes_current',filename:'[261001_01]강의(2)_필기자.pdf'}]};
  const review = load('reviewPrompt').renderReviewPrompt('간결하게 복습해줘. {교수}',detail);
  assert.equal(review, '간결하게 복습해줘.\n\n올해 담당 교수: 교수 미상');
  assert.ok(!review.includes('예정교수'));
});
test('default review uses the requested flow prompt and only one professor line', () => {
  const { DEFAULT_REVIEW_PROMPT, renderReviewPrompt } = load('reviewPrompt');
  const filename = '[261104_01] 포도알균(김범준)_박정수 v1.pdf';
  const detail = {title:'포도알균',professors:['예정교수'],date:'2026-11-04',subject:'감염과 면역',files:[
    {kind:'notes_current',filename}]};
  assert.equal(renderReviewPrompt(DEFAULT_REVIEW_PROMPT, detail),
    `${filename}\n오늘 들은 강의를 복습하고 싶어. 첨부한 올해 필기와 족보를 바탕으로 큰 흐름을 설명해줘.\n\n올해 담당 교수: 김범준`);
  assert.equal(p.reviewProfessorGuidance('[261001_01]강의(문경철김혜령)_필기자.pdf'),
    '올해 담당 교수: 문경철·김혜령');
});

test('canonical bank instructions retain professor context and priority/reference rules', () => {
  const bank = fs.readFileSync(path.join(__dirname,'../../content/prompts/bank/bankPrompt.md'),'utf8');
  assert.ok(bank.includes('{{professor_info}}'));
  assert.ok(bank.includes('올해 담당 교수와 일치하는 기출을 우선'));
  assert.ok(bank.includes('다른 교수·교수 미상 기출은 참고'));
});
