"""Main-Quiz cloze: the revealed units fill the shown blanks one by one (2026-11-12, table cloze cells shifted)."""
from tests.root_support import setup

setup()   # isolated local DB before any app import
from app import bank_personal
from app.root_learning.content import answer, front

# Stored as a generated revision wrote them (감염과 면역 261104_03 Q186, 261105_01 Q023): units that drop a
# repeated blank or merge a table row do not line up with the blanks the learner sees.
MUCOR = {'question_id': 'Q186', 'format': 'cloze',
         'question': '침습성 Aspergillus와 Mucor를 비교하시오.\n|대상|주요 침범 구조|균사 형태|\n|---|---|---|\n'
                     '|침습성 Aspergillus|{혈관}|상대적으로 가늘고 규칙적, 격막 있음|\n'
                     '|Mucor|{혈관}|{넓고 불규칙}, {격막이 없거나 드묾}, {직각에 가까운 분지}|',
         'answer': '혈관; 넓고 불규칙; 격막이 없거나 드묾; 직각에 가까운 분지',
         'answer_units': ['혈관', '넓고 불규칙', '격막이 없거나 드묾', '직각에 가까운 분지']}
PYOGENES = {'question_id': 'Q023', 'format': 'cloze',
            'question': '| 감염 | 연령군 | 위생 위험요인 |\n| --- | --- | --- |\n| 인두염 | {5–15세} | — |\n| 농피증 | {2–5세} | {불량한 위생} |',
            'answer': '인두염: 5–15세; 농피증: 2–5세, 불량한 위생',
            'answer_units': ['인두염: 5–15세', '농피증: 2–5세, 불량한 위생']}


def test_units_follow_the_shown_blanks():
    for q, units in [(MUCOR, ['혈관', '혈관', '넓고 불규칙', '격막이 없거나 드묾', '직각에 가까운 분지']),
                     (PYOGENES, ['5–15세', '2–5세', '불량한 위생'])]:
        shown = front(q)['question']
        revealed = answer(q)
        assert shown.count('{{c1}}') == len(units)
        assert revealed['answerUnits'] == units
        assert revealed['answer'] == q['answer']   # the stored answer text is kept


def test_other_formats_and_plain_cloze_keep_their_stored_units():
    assert answer({**MUCOR, 'format': 'basic'})['answerUnits'] == MUCOR['answer_units']
    plain = {**MUCOR, 'question': '{{c1}} is shown', 'answer_units': ['stored']}
    assert answer(plain)['answerUnits'] == ['stored']


def test_a_rewritten_personal_answer_still_has_no_units():
    class Edit:   # the bank_personal_edit row as apply_edit reads it
        original = PYOGENES
        question = PYOGENES['question']
        answer = '5–15세; 2–5세; 불량한 위생'
    edited = bank_personal.apply_edit(PYOGENES, Edit)
    assert edited['personalAnswer'] and answer(edited)['answerUnits'] == []
