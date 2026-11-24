"""scan2 적용 뒤 객관식 모드에서 정답만 표기가 달라 티 나는 묶음을 Codex CLI로 맞춘다(운영 쓰기 없음).

입력: <runId>/after/(apply.py가 scan2로 만든 사본)와 tells.json(검토 스크립트가 찾은 문항 목록), scan2 glossary.
출력: <runId>/scan3/chunk-0.json — scan과 같은 꼴(edits). apply.py가 scan2 다음에 이어서 적용한다.
"""
import json
import shutil
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from studyez_llm import codex

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scan import ROOT, SCHEMA, WORK  # noqa: E402

RULES = """\
너는 의대 복습 퀴즈의 용어 표기만 고치는 편집자다. 내용·의미·난이도는 바꾸지 않는다.

배경: 이 강의 문항의 의학용어를 강의록 표기(대개 영어, 어려운 말은 `english(한글)` 병기)로 바꿨다. 그 결과 객관식 모드에서
정답 보기와 오답 보기의 꼴이 달라져 정답이 티 나는 묶음이 생겼다. 예: 정답 `sacroiliac joint(천장관절)`, 오답 `무릎관절`·`발목관절`.

할 일: questions.json의 각 문항에서 correct(정답 보기들)와 choices(오답 보기들)가 같은 묶음 안에서 언어·병기 꼴이 비슷해 보이게 맞춘다.
- 먼저 오답을 정답 꼴에 맞춘다. 정답이 영어면 오답도 영어 의학용어로, 정답이 `english(한글)`이면 오답도 `english(한글)`로.
  오답 개념을 이 강의자료가 부르는 말이 있으면 그 말, 없으면 표준 영어 의학용어. 아래 「이 강의 표기」에 있는 개념은 그 꼴 그대로.
- 정답이 한글로 남았는데 오답이 영어라면(예: 정답 `감염`, 오답 `retinopathy`), 오답을 자연스러운 한국어 의학용어로 되돌리거나
  정답을 강의 표기로 바꾸는 것 중 강의자료에 맞는 쪽을 고른다. 강의가 그 말을 한국어로 쓰면 오답을 한국어로 한다.
- 목록형은 정답 보기가 여럿이다. 정답들끼리 꼴이 섞여 있으면(한글 몇 개·영어 몇 개) 오답도 비슷한 비율로 섞어 어느 한 꼴이
  정답의 표지가 되지 않게 한다.
- 오답의 why_wrong 안 같은 용어도 같은 꼴로 바꾼다.
- 이미 티 나지 않으면 그 문항은 edits에 넣지 않는다. 새 정보·설명을 더하지 않는다. 오답끼리·정답과 같은 글이 되지 않게 한다.

출력(scan과 같은 꼴):
- choice_replacements: 오답 하나(choice_id)에 적용할 {from, to}. from은 그 오답의 text 또는 why_wrong에 실제로 있는 부분 문자열.
- replacements: 정답 쪽을 바꿀 때만. 그 문항의 발문·정답·채점 단위·해설·보기 전체에 적용된다. 발문에 정답을 드러내지 않는다.
- glossary: 이번에 새로 정한 표기만(없으면 빈 배열). basis: 근거(강의자료 위치·표기 또는 「표준 영어 용어」).
"""


def payload(rid, qids):
    after = WORK / rid / 'after'
    doc = json.loads((after / 'document.json').read_text(encoding='utf-8'))
    mcq = json.loads((after / 'root_mcq.json').read_text(encoding='utf-8'))['questions']
    original = json.loads((WORK / rid / 'before' / 'root_mcq.json').read_text(encoding='utf-8'))['questions']
    out = []
    for q in doc['bank_snapshot']['questions']:
        if q['question_id'] not in qids:
            continue
        units = q.get('answer_units') or [q['answer']]
        out.append({'question_id': q['question_id'], 'format': q['format'], 'question': q['question'],
                    'answer': q['answer'], 'answer_units': units, 'explanation': q.get('explanation', ''),
                    # choice_id는 원본 ID(apply.py가 원본 선지에 치환을 걸고 ID는 마지막에 다시 계산한다). 순서는 같다.
                    'choices': [{'choice_id': o['id'], 'text': w['text'], 'why_wrong': w.get('why_wrong', ''),
                                 'group': w.get('group'),
                                 'correct_in_group': [units[w['group']]] if isinstance(w.get('group'), int) else units}
                                for w, o in zip(mcq[q['question_id']].get('wrong') or [],
                                                original[q['question_id']].get('wrong') or [])]})
    return doc, out


def align(rid, qids):
    out = WORK / rid / 'scan3' / 'chunk-0.json'
    if out.exists():
        return rid, len(json.loads(out.read_text(encoding='utf-8'))['edits'])
    doc, rows = payload(rid, set(qids))
    glossary = json.loads((WORK / rid / 'scan2' / 'glossary.json').read_text(encoding='utf-8'))
    material = ROOT / 'runs/_root-generation' / doc['revision'].removeprefix('auto-') / 'generation/material'
    with tempfile.TemporaryDirectory(prefix='sez-align-') as temp:
        ws = Path(temp)
        shutil.copytree(material, ws / 'material')
        (ws / 'questions.json').write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding='utf-8')
        known = '\n'.join(f'- {g["korean"]} → {g["lecture_form"]}' for g in glossary)
        prompt = (RULES + f'\n이 강의 표기:\n{known}\n\n강의: 「{doc["title"]}」. questions.json에 문항 {len(rows)}개. '
                  '강의자료는 material/*.md(쪽마다 머리), 글이 없는 쪽은 material/*.png. JSON만 반환한다.')
        info = codex.run(prompt, blind=False, cwd=ws, schema=SCHEMA, timeout=3000,
                         label=f'선지 표기 맞춤 {rid}', system='Edit only terminology notation of answer choices. Preserve meaning.')
    value = json.loads(info['text'])
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(value, ensure_ascii=False, indent=1), encoding='utf-8')
    return rid, len(value['edits'])


if __name__ == '__main__':
    tells = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
    with ThreadPoolExecutor(max_workers=len(tells)) as pool:
        for future in [pool.submit(align, rid, qids) for rid, qids in tells.items()]:
            try:
                print('DONE', *future.result(), flush=True)
            except Exception as error:  # noqa: BLE001
                print('FAILED', repr(error)[:300], flush=True)
