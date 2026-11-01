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
  assert.ok(review.includes('시간표나 족보의 올해 담당 표기와 다르면'));
  const preview = load('previewPrompt').renderPreviewPrompt('{교수}\n{파일명}',detail);
  assert.ok(preview.startsWith('유경상\n[251001_01]'));
  assert.ok(!preview.includes('복습 담당 교수 확인'));
});
test('custom review templates still receive the source check and unknowns are not replaced by timetable guesses', () => {
  const detail = {title:'강의',professors:['예정교수'],date:'2026-11-01',subject:'과목',files:[
    {kind:'notes_current',filename:'[261001_01]강의(2)_필기자.pdf'}]};
  const review = load('reviewPrompt').renderReviewPrompt('간결하게 복습해줘. {교수}',detail);
  assert.ok(review.startsWith('간결하게 복습해줘.'));
  assert.ok(review.includes('교수 미상'));
  assert.ok(!review.includes('예정교수'));
});
test('canonical bank instructions check actual notes and retain other professors as references', () => {
  const bank = fs.readFileSync(path.join(__dirname,'../../content/prompts/bank/bankPrompt.md'),'utf8');
  assert.match(bank,/Version: 1\.79/);
  assert.ok(bank.includes('올해 실제 담당 교수는 첨부한 올해 필기의 파일명'));
  assert.ok(bank.includes('필기자 이름을 교수로 읽지 않으며'));
  assert.ok(bank.includes('다른 교수·교수 미상 기출은 참고'));
});
