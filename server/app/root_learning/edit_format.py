"""Main-Quiz 「문제 수정·제보」의 형식 바꾸기(2026-11-17, docs/changes/2026-11-17-personal-edit-format).

사용자 「유형은 전부 다 바꿀 수 있도록. 다만 적당한 형식 제한이 걸리긴 하겠지」. Main-Quiz가 다루는 여섯 형식
(studyez_contracts.roots.validate) 사이에서 바꾸고, 형식마다 판 문항이 지키는 최소 조건만 본다.
저장은 bank_personal_edit.structure, 보이는 모양은 bank_personal.with_structure.
"""
from __future__ import annotations

from typing import Literal

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field
from studyez_contracts.bank.cloze import INLINE

FORMATS = ('basic', 'list', 'cloze', 'ox', 'mcq', 'multi_select')
LABELS = {'basic': '주관식', 'list': '나열', 'cloze': '빈칸', 'ox': 'OX', 'mcq': '객관식', 'multi_select': '복수 선택'}
CHOICE = ('mcq', 'multi_select')


class Option(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: str = Field(max_length=16)
    text: str = Field(max_length=2000)


class Structure(BaseModel):
    model_config = ConfigDict(extra='forbid')
    format: Literal['basic', 'list', 'cloze', 'ox', 'mcq', 'multi_select']
    mcq_mode: Literal['none', 'recall_first', 'comparison'] = 'none'
    options: list[Option] = Field(default_factory=list, max_length=8)
    correct_option_ids: list[str] = Field(default_factory=list, max_length=8)
    explanation: str = Field(default='', max_length=12000)


def _fail(message):
    raise HTTPException(422, message)


def build(structure: Structure, question: str, answer: str) -> tuple[dict, str]:
    """(저장할 structure, 저장할 정답 글). 형식 조건이 안 맞으면 422."""
    fmt = structure.format
    units, options, correct, mode = [], [], [], 'none'
    if fmt == 'basic':
        if not answer:
            _fail('정답을 입력하세요.')
    elif fmt == 'list':
        units = [line.strip() for line in answer.splitlines() if line.strip()]
        if len(units) < 2:
            _fail('나열은 정답을 한 줄에 하나씩 2개 이상 입력하세요.')
        answer = '\n'.join(units)
    elif fmt == 'cloze':
        units = [m[1].strip() for m in INLINE.finditer(question)]
        if not units or not all(units):
            _fail('빈칸은 발문에서 가릴 답을 {정답}처럼 중괄호로 1개 이상 감싸세요.')
        if '{{' in INLINE.sub('', question) or '}}' in INLINE.sub('', question):
            _fail('빈칸 표시는 {정답}처럼 중괄호 한 겹으로 쓰세요.')
        answer = '; '.join(units)
    elif fmt == 'ox':
        answer = answer.strip().upper()
        if answer not in ('O', 'X'):
            _fail('OX 정답은 O 또는 X로 고르세요.')
    else:
        options = [{'id': o.id.strip(), 'text': o.text.strip()} for o in structure.options]
        ids = [o['id'] for o in options]
        if len(options) < 2 or not all(ids) or len(set(ids)) != len(ids) or not all(o['text'] for o in options):
            _fail('보기를 2개 이상(8개까지), 서로 다른 내용으로 입력하세요.')
        correct = list(dict.fromkeys(i.strip() for i in structure.correct_option_ids))
        if not correct or not set(correct) <= set(ids):
            _fail('정답 보기를 고르세요.')
        if fmt == 'mcq' and len(correct) != 1:
            _fail('객관식 정답은 보기 하나입니다.')
        if fmt == 'multi_select' and len(correct) >= len(ids):
            _fail('복수 선택은 모든 보기가 정답일 수 없습니다.')
        mode = structure.mcq_mode if structure.mcq_mode != 'none' else 'comparison'
        answer = '\n'.join(o['text'] for o in options if o['id'] in correct)
    return ({'format': fmt, 'mcq_mode': mode, 'answer_units': units, 'options': options,
             'correct_option_ids': correct, 'explanation': structure.explanation.strip()}, answer)


def shape(q: dict) -> dict:
    """수정창이 읽는 문항 모양."""
    return {'question': q['question'], 'answer': q['answer'], 'explanation': q.get('explanation', ''),
            'format': q.get('format', 'basic'), 'mcqMode': q.get('mcq_mode', 'none'),
            'options': [{'id': o['id'], 'text': o['text']} for o in q.get('options', [])],
            'correctOptionIds': list(q.get('correct_option_ids', []))}
