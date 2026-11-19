"""CBL 3에 붙어 있던 기존 족보 표시·채점 기록(jokbo_mark)의 강의를 CBL 4·5로 옮긴다.

    python docs/changes/2026-11-20-cbl45-jokbo/move_marks.py            # 읽기만: 옮길 행 수
    python docs/changes/2026-11-20-cbl45-jokbo/move_marks.py --apply    # 한 트랜잭션으로 반영

문항 ID·밴드·횟수·시각은 바꾸지 않고 event_id만 바꾼다. CBL 4·5 문서를 올린 뒤에 돌린다
(오답노트는 mark.event_id의 문서에서 문항을 찾으므로, 옮기기 전에는 이 문항들이 오답노트에서 빠진다).
server/.env가 가리키는 DB를 쓴다. 개인 기록 내용은 출력하지 않는다.
"""
import argparse
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "server"))
os.chdir(ROOT / "server")

from sqlalchemy import func, select, update  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models import JokboMark  # noqa: E402


def plan() -> tuple[str, dict[str, list[str]]]:
    moves = json.loads((HERE / "moves.json").read_text(encoding="utf-8"))
    out = {t["event"]: [f"pe_{y}_0c_{n:03d}" for y, ns in t["items"].items() for n in ns]
           for t in moves["targets"].values()}
    return moves["fromEvent"], out


def counts(db, targets: dict[str, list[str]]) -> dict[str, dict[str, list[int]]]:
    """대상 강의별로, 그 문항들의 기록이 지금 어느 event_id에 몇 행·몇 명 있는지."""
    out = {}
    for event, items in targets.items():
        rows = db.execute(select(JokboMark.event_id, func.count(), func.count(func.distinct(JokboMark.user_id)))
                          .where(JokboMark.item_id.in_(items)).group_by(JokboMark.event_id)).all()
        out[event] = {e: [n, u] for e, n, u in rows}
    return out


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--apply", action="store_true")
    a = p.parse_args()
    source, targets = plan()
    with SessionLocal() as db:
        before = counts(db, targets)
        print(json.dumps({"before [rows, users]": before}, ensure_ascii=False, indent=1))
        if not a.apply:
            return
        changed = 0
        for event, items in targets.items():
            r = db.execute(update(JokboMark)
                           .where(JokboMark.event_id == source, JokboMark.item_id.in_(items))
                           .values(event_id=event))
            changed += r.rowcount
        after = counts(db, targets)
        left = sum(c.get(source, [0])[0] for c in after.values())
        if left:
            db.rollback()
            raise SystemExit(f"CBL 3에 남은 행 {left} — 되돌림")
        db.commit()
        print(json.dumps({"changed": changed, "after": after}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
