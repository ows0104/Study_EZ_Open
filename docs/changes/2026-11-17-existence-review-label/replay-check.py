"""실데이터 재현 — 운영 공개판 사본에 이름표 규칙만 다시 돌려 센다 (R6).

사본은 저장소 밖에 둔다: `<DUMPS>/gen_<runId>.json`, 운영 `root_generation`의 읽기 전용 조회본
(`{'packet': …, 'result': …}`). 운영에 쓰지 않는다. 기본 경로는 `C:\\sez\\vero`이고 첫 인자로 바꿀 수 있다.

    python docs/changes/2026-11-17-existence-review-label/replay-check.py [덤프폴더]

2026-11-17 실측: 받아온 문항에 붙은 이름표 고침 전 47 → R2만 10 → R1+R2 **0**.
이번 실행이 쓴 문항의 이름표 91개는 그대로 남는다.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from studyez_contracts.roots import discriminate as dis, presuppose as pre

DUMPS = Path(sys.argv[1] if len(sys.argv) > 1 else r'C:\sez\vero')
RUNS = ['261116_02', '261116_03', '261116_05', '261116_06']


def labels(fn, recs, brief, bank, **kw):
    """이름표가 붙은 문항 ID. ctx는 실제 실행과 같게 그 묶음의 문항 전부를 넘긴다."""
    ctx = fn({'questions': [dict(q) for q in bank['questions']]}, brief, recs, bank, **kw)
    return [r['question_id'] for r in (ctx.get('existence') or ctx.get('discrimination') or [])]


def before(bank, recs):
    """고침 전 규칙: 전제·역방향 포인트가 point_ids에 있으면 그 문항은 그 목표의 것."""
    pids = {r['point_id'] for r in recs if r['point_id']}
    return [q['question_id'] for q in bank['questions'] if set(q.get('point_ids') or []) & pids]


def main():
    total = {'before': 0, 'r2': 0, 'both': 0, 'kept': 0}
    for run in RUNS:
        d = json.loads((DUMPS / f'gen_{run}.json').read_text(encoding='utf-8'))
        man, brief, doc = d['result']['manifest'], d['result']['brief'], d['result']['document']
        bank = {'questions': doc['bank_snapshot']['questions']}
        ib = man['initialBank']
        intake = {q['question_id'] for q in (ib['questions'] if isinstance(ib, dict) else ib)}
        print(f'\n## {run}')
        for name, fn, recs in (('존재', pre.mark_review, man['presuppositions']),
                               ('역방향', dis.mark_review, man.get('discriminations') or [])):
            if not recs:
                continue
            old = [q for q in before(bank, recs) if q in intake]
            r2 = [q for q in labels(fn, recs, brief, bank) if q in intake]
            both = labels(fn, recs, brief, bank, exclude=intake)
            print(f'   {name}: 받아온 문항에 붙은 이름표 — 고침 전 {len(old)} · R2만 {len(r2)} · '
                  f'R1+R2 {len([q for q in both if q in intake])}'
                  f' | 이번 실행이 쓴 문항 {len([q for q in both if q not in intake])}')
            total['before'] += len(old)
            total['r2'] += len(r2)
            total['both'] += len([q for q in both if q in intake])
            total['kept'] += len([q for q in both if q not in intake])
    print(f"\n합계 — 받아온 문항에 붙은 이름표: 고침 전 {total['before']} · R2만 {total['r2']} · "
          f"R1+R2 {total['both']}")
    print(f"이번 실행이 쓴 문항의 이름표(남아야 한다): {total['kept']}")
    return 0 if total['both'] == 0 else 1


if __name__ == '__main__':
    raise SystemExit(main())
