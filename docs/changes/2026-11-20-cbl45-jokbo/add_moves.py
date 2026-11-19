"""moves.json의 CBL 4·5 이동을 jokbo-solve 교정 파일(git 밖)에 얹는다. 여러 번 돌려도 같다.

    python docs/changes/2026-11-20-cbl45-jokbo/add_moves.py [--root <jokbo-solve 폴더>]

기존 교정(그림·선지)은 그대로 두고 note·evidence에 이동 사유를 덧붙이며 moveTo만 정한다.
"""
import argparse
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
DEFAULT = ROOT / "runs" / "_materials" / "감염과 면역" / "jokbo-solve"
AMGI_SET = Path.home() / "amgi" / "data" / "pastexam"


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--root", type=Path, default=DEFAULT)
    a = p.parse_args()
    moves = json.loads((HERE / "moves.json").read_text(encoding="utf-8"))
    set_id = moves["setId"]
    ids = {it["pastExamItemId"] for it in
           json.loads((AMGI_SET / f"{set_id}.json").read_text(encoding="utf-8"))["items"]}
    path = a.root / "fixes" / f"{set_id}.json"
    fixes = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    moved = 0
    for key, t in moves["targets"].items():
        for year, nums in t["items"].items():
            for n in nums:
                item = f"pe_{year}_0c_{n:03d}"
                if item not in ids:
                    raise SystemExit(f"원천에 없는 문항: {item}")
                note = (f"원본에서 「★」와 「{t['title']}」 제목이 줄이 나뉘어 원천이 구획을 못 잡아 "
                        f"CBL 3 세트에 들어 있어 {key}로 옮김.")
                ev = f"2025 감염과 면역 족보.pdf {t['pages']} ({t['title']} 머리 아래 {year}년 {n}번), 답안지 p.116-117"
                f = fixes.setdefault(item, {"note": note, "evidence": ev})
                if note not in f["note"]:
                    f["note"] += " " + note
                if ev not in f["evidence"]:
                    f["evidence"] += "; " + ev
                f["moveTo"] = [key]
                moved += 1
    stay = {f"pe_{y}_0c_{n:03d}" for y, ns in moves["staysInCbl3"].items() for n in ns}
    left = ids - {i for i, f in fixes.items() if f.get("moveTo")}
    if left != stay:
        raise SystemExit(f"CBL 3에 남는 문항이 정답표와 다름: {sorted(left)}")
    path.write_text(json.dumps(fixes, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"moved": moved, "staysInCbl3": sorted(left), "file": str(path)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
