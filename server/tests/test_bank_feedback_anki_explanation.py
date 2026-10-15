"""Separate OX rationale survives the offline Anki export with an X-only answer."""
import os
import tempfile
from pathlib import Path

TMP = Path(tempfile.mkdtemp(prefix='studyez-feedback-anki-'))
os.environ.update(ENVIRONMENT='local-test', DATABASE_URL=f"sqlite:///{(TMP / 'test.db').as_posix()}",
    STUDYEZ_LOCAL_STORAGE_DIR=str(TMP / 'storage'), RUNNER_TOKEN='runner-token')

from app.bank_anki import render_answer, render_question


def main():
    q = {'question_id': 'Q043', 'format': 'ox', 'question': '검사 결과가 양성이다. (O/X)',
         'answer': 'X', 'answer_units': ['X'], 'source_refs': [],
         'explanation': '검사 결과는 음성이다.\nA < B & C'}
    front = render_question(q)
    back = render_answer(q, {}, {}, [])
    assert q['explanation'] not in front and '해설' not in front
    assert '<p>X</p>' in back
    assert '검사 결과는 음성이다.<br>A &lt; B &amp; C' in back
    assert back.count('<b>해설</b>') == 1
    q['explanation'] = ''
    assert '<b>해설</b>' not in render_answer(q, {}, {}, [])
    print('PASS offline OX explanation is present only on the answer side and safely escaped')


if __name__ == '__main__':
    main()
