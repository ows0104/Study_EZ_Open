"""여러 판의 카드를 **출처를 가린 채** 한 세션에게 판정시킨다.

프롬프트 문구를 고르는 고리가 너무 비쌌다. 2026-09-06 에 한 편(`260901_01`)을 아홉 번
돌려 프롬프트를 고쳤는데, **실행끼리 비교한 주장이 하나도 안 남았다** — 같은 자료
같은 편인데 cloze 가 6~16장, 재현 같음이 78~91%, 결함이 0~6장으로 흔들려서 만들려던
효과가 그 폭에 통째로 묻혔다. 관측 하나에 30분·$15 였다.

여기서는 **이미 만들어 둔 카드**를 쓴다. 판마다 카드를 뽑아 섞고, 어느 판에서 왔는지
가린 채 판정을 받는다. 출처는 결과 파일에서만 다시 붙인다.

    한 번 돌리기   30분 · $15 · 카드 100장 · 실행 간 잡음에 묻힘
    한 번 심판     30초 · $0.2 · 카드 수백장 · 같은 세션이 같은 자를 댄다

**같은 세션 안에서 견주는 것이 요점이다.** 판마다 따로 물으면 세션 간 편차가 다시
끼어든다. 그래서 섞어서 한 번에 넣는다.

사용:
    python -m quizgen.judge cloze runs/260901_01/main/260906-1147                                   runs/260901_01/main/260906-1448
    python -m quizgen.judge cloze runs/2609*/main/* --n 60

## 그 아홉 판이 어느 자리에 있나

`out/exp_260901_01_v*` 였던 것이 2026-09-15 에 `runs/260901_01/main/<판>/` 으로 접혔다
(`docs/runs-layout.md` 5단계). 대응은 이렇다 — 각 판의 cloze 수가 첫 판정이 적어 둔
값과 한 장도 안 다른 것으로 확인했다.

    v2 260905-1208   v3 260905-1729   v4 260905-1829   v5 260905-1950
    v6 260906-0215   v7 260906-1147   v8 260906-1341   v9 260906-1448

첫 판정(2026-09-06): **v5 11장 91% · v6 16장 56% · v7 16장 94% · v8 11장 82% ·
v9 6장 83%.** v7 이 이겨서 그 cloze 절을 되살렸다(`b2b4326`).

**지금 프롬프트는 v7 그 자체가 아니다.** v7 의 cloze 절에서 관리자가 뒤집은 넷을
걷어낸 조합이고, **그 조합은 아직 심판을 안 받았다.** 그것이 이 도구의 남은 숙제다.

## 그 아홉 번에 프롬프트는 제대로 들어갔다 (2026-09-15 확인)

`quizgen/CLAUDE.md` 가 한동안 「그 아홉 번도 같은 폴더를 반복해서 썼다 — 잡음 중
얼마가 옛 프롬프트 때문인지 알 수 없다」고 적고 있었다. **틀렸다.** 판마다 자기 폴더에
자기 프롬프트를 실행 시작 시각에 썼고 **파트 수가 아홉 번 내내 같다**(cards 2 ·
plan 2 · context 3). `1of2` 가 `1of3` 을 이기는 자리는 파트 수가 달라질 때만 열린다.

그러니 그 흔들림은 **같은 프롬프트 같은 자료로도 생기는 것**이고, 그것이 이 도구가
있는 이유다. **심판이 약한 이유는 다른 데 있다** — 한 번 돌린 한 판정이고 cloze
60장이다. 심판을 두 번 돌리면 얼마나 흔들리는지는 아직 안 재 봤다.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

from .reproduce import (PROMPTS, chunks, front_of, numbered_front, run_chunks,
                        task_text)

RUBRICS = {"cloze": ("judge_cloze.md", "cloze")}


def cards_of(d: Path, fmt: str) -> list[dict]:
    """그 판의 카드. 빌드에 실제로 들어간 것(`items.reproduced.json`)을 쓴다."""
    for name in ("items.reproduced.json", "items.checked.json"):
        p = d / name
        if not p.exists():
            continue
        raw = json.loads(p.read_text(encoding="utf-8"))
        cs = raw.get("cards", raw)
        return [c for c in cs if isinstance(c, dict) and c.get("card_format") == fmt]
    return []


def pool(dirs: list[Path], fmt: str, n: int | None, seed: int) -> list[dict]:
    """판마다 카드를 뽑아 섞는다. 출처는 여기서만 안다."""
    rows = []
    for d in dirs:
        cs = cards_of(d, fmt)
        if n and len(cs) > n:
            cs = random.Random(seed).sample(cs, n)
        for c in cs:
            rows.append({"src": d.name, "card": c})
    random.Random(seed).shuffle(rows)
    for i, r in enumerate(rows, 1):
        r["jid"] = f"j{i:03d}"
    return rows


def build(rows: list[dict], rubric: str, out_path: Path | None) -> str:
    lines = []
    for r in rows:
        c = r["card"]
        front = numbered_front(c) if c["card_format"] == "cloze" else front_of(c)
        a = (c.get("a") or "").replace("\n", " / ")
        lines.append(f"| {r['jid']} | {front} | {a} |")
    table = "\n".join(["| id | 앞면 | 정답 |", "|---|---|---|"] + lines)
    task = task_text(rubric, out_path)
    return f"{task}\n\n---\n\n# 카드 {len(rows)}장\n\n{table}\n"


def report(rows: list[dict], verdicts: dict[str, dict]) -> None:
    by = defaultdict(Counter)
    for r in rows:
        v = verdicts.get(r["jid"])
        if v:
            by[r["src"]][v.get("verdict", "?")] += 1
    print(f"\n{'판':22}{'n':>5}{'ok':>6}{'weak':>6}{'bad':>6}{'ok율':>7}")
    for src in sorted(by):
        c = by[src]
        t = sum(c.values())
        print(f"{src:22}{t:5}{c['ok']:6}{c['weak']:6}{c['bad']:6}{c['ok'] / t * 100:6.0f}%")
    print("\n어긋났다고 본 카드 —")
    for r in rows:
        v = verdicts.get(r["jid"]) or {}
        if v.get("verdict") in ("weak", "bad"):
            c = r["card"]
            front = numbered_front(c) if c["card_format"] == "cloze" else front_of(c)
            print(f"  [{v['verdict']:4}] {r['src']:20} {front[:74]}")
            if v.get("why"):
                print(f"          {v['why'][:96]}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="여러 판의 카드를 출처를 가리고 판정한다")
    ap.add_argument("rubric", choices=sorted(RUBRICS))
    ap.add_argument("dirs", nargs="+", help="비교할 실행 폴더들")
    ap.add_argument("-o", "--out", help="결과 JSON. 기본은 out/judge.<rubric>.json")
    ap.add_argument("--n", type=int, help="판마다 뽑을 카드 수 (기본: 전부)")
    ap.add_argument("--seed", type=int, default=0, help="뽑기·섞기 씨앗")
    ap.add_argument("--model", help="빈 세션에 쓸 모델")
    ap.add_argument("--chunk", type=int, default=60, help="한 세션에 넣을 카드 수")
    ap.add_argument("--timeout", type=int, default=1800)
    ap.add_argument("--jobs", type=int, default=2)
    args = ap.parse_args(argv)

    rubric, fmt = RUBRICS[args.rubric]
    dirs = [Path(d) for d in args.dirs]
    missing = [d for d in dirs if not d.is_dir()]
    if missing:
        print(f"없는 폴더: {', '.join(str(d) for d in missing)}")
        return 1

    rows = pool(dirs, fmt, args.n, args.seed)
    if not rows:
        print(f"{fmt} 카드가 한 장도 없다.")
        return 1
    per = Counter(r["src"] for r in rows)
    print(f"판 {len(dirs)}개 · {fmt} 카드 {len(rows)}장")
    for s in sorted(per):
        print(f"   {s:22}{per[s]:4}장")

    batches = chunks(rows, args.chunk)
    got = run_chunks(batches, lambda b: build(b, rubric, None), "judgements",
                     lambda r: r["jid"], model=args.model, timeout=args.timeout,
                     retries=1, label="심판", jobs=args.jobs, out=dirs[0])
    if not got:
        print("한 장도 받지 못했다.")
        return 1
    verdicts = {g["id"]: g for g in got}
    report(rows, verdicts)

    out = Path(args.out) if args.out else Path("out") / f"judge.{args.rubric}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(
        {"rubric": args.rubric,
         "cards": [{"jid": r["jid"], "src": r["src"], "id": r["card"].get("id"),
                    "q": r["card"]["q"], "a": r["card"].get("a"),
                    **{k: v for k, v in (verdicts.get(r["jid"]) or {}).items() if k != "id"}}
                   for r in rows]},
        ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n→ {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
