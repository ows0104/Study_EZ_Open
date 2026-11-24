"""공개 6편의 문항·선지를 강의자료와 대조해 표기만 바꿀 목록을 Codex CLI로 받는다(운영 쓰기 없음).

입력: runs/_development/2026-11-24-term-notation-published/<runId>/before/(fetch.py), 강의자료는 그 판의
runs/_root-generation/<gid>/generation/material. 출력: <runId>/scan/chunk-<n>.json(모델 원문 그대로).
"""
import json
import shutil
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from studyez_llm import codex

ROOT = Path(r'C:\Users\ows01\Documents\Python Scripts\Study_EZ_Open')
WORK = ROOT / 'runs/_development/2026-11-24-term-notation-published'
CHUNK = 60

RULES = """\
너는 의대 복습 퀴즈의 용어 표기만 고치는 편집자다. 내용·의미·문장 구조·난이도는 바꾸지 않는다.

사용자 지시: 「답과 문제의 의학용어가 너무 한글화되어서 가끔 문제가 어려워. 강의록의 표기를 따르고 필요한 경우 병기」.
표기 규칙(이 프로젝트의 출제 원칙과 같다):
1. 강의자료(슬라이드·필기)가 그 개념을 부르는 말을 그대로 쓴다. 자료가 `macrophage`, `AV block`이라 썼는데 문항이
   「대식세포」, 「방실차단」이라 썼으면 강의 표기로 바꾼다. 자료가 한국어로 쓴 말(예: 「이형성증」)은 그대로 둔다.
2. 자료에 그 개념의 표기가 없으면 손대지 않는다(이번 작업은 이미 게시된 문항을 강의 표기에 맞추는 것뿐이다).
3. 학생이 처음 만날 만한 어려운 용어는 강의 표기 뒤에 괄호로 한국어를 병기해도 된다: `dysplasia(이형성증)`.
   쉬운 말에는 붙이지 않는다. 정답 용어의 병기는 정답 쪽(answer·answer_units·cloze 빈칸 안)에만 두고,
   발문 본문에 정답의 다른 표기를 드러내 답을 알려 주지 않는다.
4. 한 강의 안에서 같은 개념은 같은 표기·같은 병기 꼴로 쓴다.

바꾸지 않는 것: 이미 굳어진 한국어 용어를 강의도 한국어로 쓰는 경우, 조사·서술 같은 일반 문장, 숫자·약어(이미 영어인 것),
강의자료에서 확인할 수 없는 표기. 새 정보·약어 풀이·설명을 더하지 않는다. 확신이 없으면 바꾸지 않는다.

세부 기준:
- 슬라이드(교수 자료)의 표기를 필기자의 줄임말보다 앞세운다. 필기에만 있는 줄임말·구어(예: 「hetero」)는 쓰지 않는다.
- 대소문자: 문장 안에서는 소문자로 쓴다(slide 제목·글머리의 첫 대문자는 용어의 일부가 아니다). 고유명사·약어·
  유전자/단백질 표기(Crohn's disease, HLA-B27, IL-17, AS)는 자료대로.
- 병기 꼴은 개념마다 하나로 정해 그 강의의 모든 문항·선지에서 같게 쓴다. 원래 문항이 「한글(english)」로 병기했으면
  지우지 말고 「english(한글)」로 순서만 바꾼다. 쉬운 말은 병기 없이 강의 표기만 쓴다.
- 아래 「앞 조각에서 정한 표기」에 있는 개념은 반드시 그 꼴 그대로 쓴다.

입력: questions.json의 각 문항은 question(발문, cloze는 {정답} 빈칸 포함), answer, answer_units(채점 단위), explanation,
options(보기), choices(객관식 모드 오답: choice_id·text·why_wrong·group)다. 강의자료는 material/*.md(쪽마다
`## S1 physical PDF page N` 머리)와 material/*.png(쪽 그림)이다. 먼저 md로 찾고, md에 글이 없거나 애매한 쪽만 png를 연다.

출력: 바꿀 것이 있는 문항만 edits에 넣는다.
- replacements: 이 문항의 question·answer·answer_units·explanation·options와 choices의 text·why_wrong 전체에 똑같이
  적용할 치환 {from, to}. from은 그 문항 글에 실제로 있는 정확한 부분 문자열이다. 뒤 조사가 바뀌어야 하면 조사까지
  포함한다(「말초신경을」→「peripheral nerve를」). 정답·채점 단위·cloze 빈칸이 같이 바뀌므로 셋이 어긋나지 않는다.
- choice_replacements: 특정 오답 선지(choice_id) 하나에만 적용할 치환. 정답 표기를 강의 표기로 바꾸면 같은 묶음 오답도
  같은 언어·같은 병기 꼴이어야 정답이 티 나지 않는다. 오답의 개념을 이 강의자료가 부르는 말이 있으면 그 말, 없으면
  표준 영어 의학용어로 맞춘다. 오답끼리·정답과 같은 글이 되지 않게 한다.
- basis: 근거가 된 강의자료 위치와 표기(예: 「S1 p.33 'Dactylitis', p.19 'osteoclast'」).
"""

SCHEMA = {
    'type': 'object', 'additionalProperties': False, 'required': ['glossary', 'edits'],
    'properties': {
     'glossary': {'type': 'array', 'items': {
        'type': 'object', 'additionalProperties': False, 'required': ['korean', 'lecture_form', 'basis'],
        'properties': {'korean': {'type': 'string'}, 'lecture_form': {'type': 'string'}, 'basis': {'type': 'string'}}}},
     'edits': {'type': 'array', 'items': {
        'type': 'object', 'additionalProperties': False,
        'required': ['question_id', 'replacements', 'choice_replacements', 'basis'],
        'properties': {
            'question_id': {'type': 'string'},
            'replacements': {'type': 'array', 'items': {
                'type': 'object', 'additionalProperties': False, 'required': ['from', 'to'],
                'properties': {'from': {'type': 'string'}, 'to': {'type': 'string'}}}},
            'choice_replacements': {'type': 'array', 'items': {
                'type': 'object', 'additionalProperties': False, 'required': ['choice_id', 'from', 'to'],
                'properties': {'choice_id': {'type': 'string'}, 'from': {'type': 'string'}, 'to': {'type': 'string'}}}},
            'basis': {'type': 'string'}}}}}}


def payload(doc, mcq):
    rows = (mcq or {}).get('questions') or {}
    out = []
    for q in doc['bank_snapshot']['questions']:
        row = rows.get(q['question_id']) or {}
        out.append({'question_id': q['question_id'], 'format': q['format'], 'question': q['question'],
                    'answer': q['answer'], 'answer_units': q.get('answer_units', []),
                    'explanation': q.get('explanation', ''),
                    'options': [o.get('text', '') for o in q.get('options') or []],
                    'choices': [{'choice_id': w['id'], 'text': w['text'], 'why_wrong': w.get('why_wrong', ''),
                                 'group': w.get('group')} for w in row.get('wrong') or []]})
    return out


def jobs(rid):
    before = WORK / rid / 'before'
    doc = json.loads((before / 'document.json').read_text(encoding='utf-8'))
    mcq_path = before / 'root_mcq.json'
    mcq = json.loads(mcq_path.read_text(encoding='utf-8')) if mcq_path.exists() else None
    material = ROOT / 'runs/_root-generation' / doc['revision'].removeprefix('auto-') / 'generation/material'
    assert material.is_dir(), material
    rows = payload(doc, mcq)
    return [(rid, doc['title'], material, n, rows[i:i + CHUNK]) for n, i in enumerate(range(0, len(rows), CHUNK))]


OUTDIR = 'scan2'


def scan(job, glossary):
    rid, title, material, n, rows = job
    out = WORK / rid / OUTDIR / f'chunk-{n}.json'
    if out.exists():
        return json.loads(out.read_text(encoding='utf-8'))
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='sez-term-') as temp:
        ws = Path(temp)
        shutil.copytree(material, ws / 'material')
        (ws / 'questions.json').write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding='utf-8')
        known = '\n'.join(f'- {g["korean"]} → {g["lecture_form"]}' for g in glossary) or '(없음 — 첫 조각)'
        prompt = (RULES + f'\n앞 조각에서 정한 표기:\n{known}\n\n강의: 「{title}」. questions.json에 문항 {len(rows)}개가 있다. '
                  'glossary에는 이 조각에서 새로 정한 개념의 표기만 적는다. material과 questions.json만 쓴다. JSON만 반환한다.')
        info = codex.run(prompt, blind=False, cwd=ws, schema=SCHEMA, timeout=3000,
                         label=f'용어 표기 {rid} #{n}', system='Edit only terminology notation. Preserve meaning.')
    value = json.loads(info['text'])
    out.write_text(json.dumps(value, ensure_ascii=False, indent=1), encoding='utf-8')
    return value


def lecture(rid):
    """한 강의의 조각은 차례로 돈다: 앞 조각이 정한 표기를 뒤 조각이 그대로 쓴다(한 강의 안 통일)."""
    glossary, done = [], []
    for job in jobs(rid):
        value = scan(job, glossary)
        glossary += value['glossary']
        done.append(len(value['edits']))
        print(rid, job[3], len(value['edits']), flush=True)
    (WORK / rid / OUTDIR / 'glossary.json').write_text(json.dumps(glossary, ensure_ascii=False, indent=1), encoding='utf-8')
    return rid, done


if __name__ == '__main__':
    runs = sys.argv[1:] or ['261123_01', '261123_02', '261123_03', '261123_05', '261123_06', '261123_07']
    with ThreadPoolExecutor(max_workers=len(runs)) as pool:
        for future in [pool.submit(lecture, rid) for rid in runs]:
            try:
                print('DONE', *future.result(), flush=True)
            except Exception as error:  # noqa: BLE001 — 실패한 강의는 다시 돌리면 끝난 조각을 건너뛴다
                print('FAILED', repr(error)[:300], flush=True)
