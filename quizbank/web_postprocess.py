"""Reuse web-authored content; leave medical judgments to the source/answer reviews."""
import json
from pathlib import Path


def question_points(bank: dict, out: Path) -> list[dict]:
    """Index the supplied questions, explicitly without claiming source-only coverage."""
    points = [{'point_id': 'W' + q['question_id'],
               'point': q.get('exam_rationale') or q['question'],
               'source_refs': '; '.join(f"{s['source_id']} {s['locator']}" for s in q['source_refs'])}
              for q in bank['questions']]
    (out / 'point-origin.json').write_text(json.dumps({
        'origin': 'web-question-index', 'independent': False,
        'note': '웹 문항의 검수용 색인. 원본 전체의 목록 밖 누락은 별도 원본 대조에서 검수한다.'}, ensure_ascii=False), encoding='utf-8')
    (out / 'authored-points.json').write_text(json.dumps(points, ensure_ascii=False), encoding='utf-8')
    return points


POINT_CONTEXT = ('\npoint-origin.json의 origin=web-question-index이면 point-plan.json은 웹 문항 검수용 색인이다. '
                 '원본 독립 추출 결과나 완전한 학습목표 목록으로 간주하지 않는다. '
                 '원본 전체의 학습목표·강조·족보와 대조해 목록 밖의 실제 누락도 plan_issues에 반드시 기록한다. '
                 '웹 문항에 있다는 이유만으로 원본 충족으로 처리하지 않는다.')
