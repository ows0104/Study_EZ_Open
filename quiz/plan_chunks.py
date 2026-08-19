"""2단계 조각 배분을 계산해서 보여 준다. **정하지는 않는다.**

    python quiz/plan_chunks.py runs/<lecture_id>

## 왜 필요한가

`260814_05`를 조각별로 재 봤더니 벽시계를 붙잡고 있는 것이 **슬롯이 아니라 조각
크기**였다. 여덟 조각 중 c6이 26장·jkA가 25장인데 나머지는 5~14장이라 둘만 두 배였다.
동시 실행을 6에서 8로 올려도 0.9분밖에 안 준다 — 26장짜리 하나가 19.9분을 쓰기
때문이다. 반면 그 둘을 쪼개고 작은 것들을 합치면 **13.2분**이 된다(슬롯 9).

조각 소요는 카드 수에 붙는다. `260814_05`의 여덟 조각으로 맞춘 선이 이렇다
(재시도가 찍힌 c2 제외, n=7):

    소요 ≈ 4.9분 + 0.58분/카드

`260812_02`에서 족보를 jkA·jkB로 쪼갠 적이 있는데 경계 겹침 3건이 떴고 감사가 셋 다
오탐으로 판정했다 — 조각이 문항 번호로 갈렸는데 계수기는 슬라이드로 본다. 쪼개는 것
자체가 카드를 망가뜨리지는 않았지만, **겹침 신호가 늘고 그 판정에 시간이 든다.**

## 경계 규칙 (관리자 지시)

한 조각은 둘 중 하나여야 한다.

- **온전한 chunk 하나 또는 여럿을 합친 것**
- **한 chunk를 자른 조각**

쪼갠 조각을 옆 chunk와 붙이는 것은 **금지다.** 그러면 그 조각이 어느 주제의 급소도
온전히 못 받는다. 족보는 유형이 달라 **쪼개기만 되고 다른 chunk와 합치지 않는다.**

이 규칙이 이득을 깎는다는 것을 알고 쓴다 — `260814_05`는 c6과 족보를 **둘 다** 쪼개야
하는데 그러면 9조각이라, 슬롯이 8이면 벽시계가 그대로다(작업합만 4.9분 준다).
슬롯 9에서 13.2분이 된다.

## 무엇으로 예측하나

청사진의 `retrieval_target` 개수다. 두 편 열네 조각에서 target→카드 비가
**중앙값 1.08**(범위 0.77~1.54)이었고, 극단값은 전부 카드 5~10장짜리 작은 조각이라
절대 오차가 작다. 벽시계를 정하는 큰 조각들은 1.0~1.3이다.

청사진이 스스로 적는 `estimated_item_count`는 쓰지 마라 — `260814_05`에서 95라고
했는데 실제는 115장이었다(-17%). target 수가 낫다.

## 한 번 더

**여기서 나오는 것은 제안이다.** 주제 경계를 아는 것은 0.5단계이고, 쪼갠 자리가
말이 되는지는 오케스트레이터가 본다. 이 파일은 세어서 표시만 한다.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

# `260812_03` 열두 조각의 실측 (n=12). **§16a 조각 감사를 포함한 값이다.**
# 쓰기만 하던 `260814_05`는 4.89 + 0.583이었으니 §16a가 조각당 약 1분을 더한다.
FIXED_MINUTES = 5.9
PER_CARD_MINUTES = 0.64

# 오클루전이 있는 조각은 위 선보다 한참 길다. `260812_03`에서 오클루전을 낸 다섯
# 조각(c1·c6·c7·c8·c9)이 **전부 +2.2 ~ +5.5분**이었고, 없는 일곱은 −1.4 ~ +1.4분
# 안이었다. 픽셀을 재고 `render_occlusion_pair`로 앞뒤를 확인하는 값이다.
# 개수보다 '있느냐'로 갈려서 조각당 한 번만 더한다.
OCCLUSION_MINUTES = 4.0

# 두 편 열네 조각의 중앙값. 배분에는 절대 정확도가 필요 없고 상대만 맞으면 된다.
TARGET_TO_CARD = 1.1

# 벽시계가 이 안에서 같으면 조각을 적게 쓴다. 고정비 4.9분이 조각마다 붙으므로,
# 0.3분 벌자고 조각을 셋 늘리면 작업합만 15분 는다.
TOLERANCE_MINUTES = 1.0

# 실측으로 8은 확인됐다 - 조각 감사 8개를 한 번에 띄웠더니 완료 시각이 5분 안에
# 몰렸고 개별 소요는 6.4~11.0분이었다. 직렬이었으면 66분이다. 그 위는 모른다.
DEFAULT_SLOTS = 8


def minutes(cards: float) -> float:
    return FIXED_MINUTES + PER_CARD_MINUTES * cards


def wall_clock(parts: list[dict], slots: int) -> float:
    """큰 것부터 빈 슬롯에 넣는 그리디. 실제 스케줄러가 하는 것과 같은 꼴이다."""
    ends = [0.0] * max(1, slots)
    for part in sorted(parts, key=lambda p: -p["minutes"]):
        i = ends.index(min(ends))
        ends[i] += part["minutes"]
    return max(ends)


def assign_objectives(structure: dict, blueprint: dict) -> tuple[dict, list]:
    """objective를 조각에 배분한다 — `slides`의 최솟값이 어느 chunk 범위에 드는지.

    SKILL.md 2단계가 쓰는 규칙 그대로다. 족보 구간에 드는 것은 한 덩어리로 모은다.
    """
    chunk_slides = {c["id"]: tuple(c["slides"]) for c in structure.get("chunks", [])}
    jokbo = structure.get("jokbo_range")
    buckets: dict[str, list] = {}
    orphans = []
    for obj in blueprint.get("objectives", []):
        slides = obj.get("slides") or []
        if not slides:
            orphans.append(obj)
            continue
        low = min(slides)
        for cid, (a, b) in chunk_slides.items():
            if a <= low <= b:
                buckets.setdefault(cid, []).append(obj)
                break
        else:
            if jokbo and jokbo[0] <= low <= jokbo[1]:
                buckets.setdefault("jokbo", []).append(obj)
            else:
                orphans.append(obj)
    return buckets, orphans


def _targets(obj: dict) -> int:
    return len(obj.get("retrieval_targets") or [])


def _has_occlusion(objs: list[dict]) -> bool:
    """청사진이 오클루전 자리로 표시한 target이 있나.

    `occlusion_candidate`가 없는 편이면(옛 청사진) 그냥 False다 - 예측이 그만큼
    낙관적이라는 뜻이고, 그것도 정보라 출력에 적는다.
    """
    return any(t.get("occlusion_candidate")
               for o in objs for t in (o.get("retrieval_targets") or []))


def _cost(objs: list[dict]) -> float:
    base = minutes(sum(_targets(o) for o in objs) * TARGET_TO_CARD)
    return base + (OCCLUSION_MINUTES if _has_occlusion(objs) else 0.0)


def _greedy(objs: list[dict], limit: float) -> list[list[dict]] | None:
    """슬라이드 순서대로 `limit`까지 채워 담는다. 한도를 넘는 objective가 있으면 못 담는다."""
    groups, cur = [], []
    for obj in objs:
        if _cost([obj]) > limit:
            return None
        if cur and _cost(cur + [obj]) > limit:
            groups.append(cur)
            cur = []
        cur.append(obj)
    if cur:
        groups.append(cur)
    return groups


def _split_within(cid: str, objs: list[dict], limit: float) -> list[tuple] | None:
    """chunk 하나를 슬라이드 순서대로 `limit` 안에 들어가게 자른다.

    **몇 조각이 필요한지 먼저 세고, 그 수로 균등하게 나눈다.** 한도까지 채우고
    나머지를 흘리면 꼬리가 볼품없어진다 - `260812_03`에서 족보 22 target을 그렇게
    갈랐더니 20과 2로 나뉘어 벽시계가 그대로였다.

    objective 하나가 혼자 `limit`을 넘으면 못 자른다 - 그 아래로는 회수 목표가
    쪼개진다. `None`을 돌려준다.
    """
    first = _greedy(objs, limit)
    if first is None:
        return None
    k = len(first)
    if k <= 1:
        return [(cid, objs, "whole")]

    # 같은 k조각을 유지하면서 가장 큰 조각이 작아지는 한도를 찾는다.
    lo, hi = max(_cost([o]) for o in objs), limit
    best = first
    for _ in range(30):
        mid = (lo + hi) / 2
        packed = _greedy(objs, mid)
        if packed is None or len(packed) > k:
            lo = mid
        else:
            best = packed
            hi = mid
    return [(cid, g, "piece") for g in best]


def _pack(chunks: list[tuple], limit: float) -> list[tuple] | None:
    """chunk 열을 `limit` 안에 담는다. **경계 규칙을 지킨다.**

    한 조각은 둘 중 하나여야 한다 - **온전한 chunk 여럿을 합친 것**이거나
    **한 chunk를 자른 조각**이거나. 쪼갠 조각을 옆 chunk와 붙이는 것은 금지다.
    주제 하나가 두 조각에 걸리는 것까지는 감사가 받을 수 있지만, 쪼갠 반쪽에 남의
    주제 반쪽이 붙으면 그 조각은 어느 주제의 급소도 온전히 못 받는다.

    슬라이드 순서를 지키는 이유 - 조각은 `pages`로 자기 구간만 읽는다. 흩어지면
    한 조각이 강의록을 여기저기 열게 되어 조각화가 줄이려던 것을 도로 늘린다.
    """
    parts, buf = [], []
    for cid, objs in chunks:
        if _cost(objs) > limit:
            # 혼자서도 넘으면 잘라야 한다. 자른 것은 남과 못 붙으므로 먼저 비운다.
            if buf:
                parts.append(([c for c, _ in buf],
                              [o for _, os in buf for o in os], "whole"))
                buf = []
            pieces = _split_within(cid, objs, limit)
            if pieces is None:
                return None
            parts.extend(([c], os, kind) for c, os, kind in pieces)
        else:
            if buf and _cost([o for _, os in buf for o in os] + objs) > limit:
                parts.append(([c for c, _ in buf],
                              [o for _, os in buf for o in os], "whole"))
                buf = []
            buf.append((cid, objs))
    if buf:
        parts.append(([c for c, _ in buf],
                      [o for _, os in buf for o in os], "whole"))
    return parts


def _best_for(seqs: list[list[tuple]], k: int) -> tuple[float, list[tuple]] | None:
    """조각을 `k`개 이하로 쓸 때 낼 수 있는 가장 작은 벽시계.

    `seqs`는 채널별 chunk 열이다 - 강의록과 족보는 읽는 파일이 달라 한 조각에 섞을
    수 없다. 족보는 그래서 쪼개기만 되고 합치기는 안 된다.
    """
    lo = max((_cost([o]) for seq in seqs for _, objs in seq for o in objs),
             default=0.0)
    hi = sum(_cost([o for _, objs in seq for o in objs]) for seq in seqs if seq) or lo
    if lo == 0:
        return None
    best = None
    for _ in range(40):
        mid = (lo + hi) / 2
        packed = [_pack(seq, mid) for seq in seqs if seq]
        if any(p is None for p in packed) or sum(len(p) for p in packed) > k:
            lo = mid
        else:
            best = [g for p in packed for g in p]
            hi = mid
    if best is None:
        return None
    return wall_clock([_part("x", objs) for _, objs, _ in best], k), best


def rebalance(buckets: dict[str, list], slots: int,
              tolerance: float = 1.0) -> list[dict]:
    """슬롯 안에서 예상 벽시계가 가장 작아지도록 objective를 다시 나눈다.

    쪼개기만으로는 안 된다. `260814_05`는 이미 여덟 조각이라 슬롯이 꽉 차 있었고,
    c6(target 20)을 쪼개려면 c7(4)·c8(5)을 먼저 합쳐 자리를 비워야 했다. 그래서
    기존 경계를 지우고 **처음부터 다시 담는다.**

    **조각을 적게 쓰는 쪽을 우선한다.** 고정비 4.9분이 조각마다 붙으므로, 벽시계가
    `tolerance`분 안에서 같다면 적은 쪽이 낫다 - 작업합만 늘리는 분할을 막는다.
    """
    okey = lambda o: (min(o.get("slides") or [0]), str(o.get("id")))  # noqa: E731
    lecture, jokbo = [], []
    for cid, objs in buckets.items():
        (jokbo if cid == "jokbo" else lecture).append((cid, sorted(objs, key=okey)))
    ckey = lambda c: min(min(o.get("slides") or [0]) for o in c[1])  # noqa: E731
    seqs = [sorted(lecture, key=ckey), sorted(jokbo, key=ckey)]

    options = {}
    for k in range(1, max(1, slots) + 1):
        found = _best_for(seqs, k)
        if found:
            options[k] = found
    if not options:
        return sorted((_part(cid, objs) for cid, objs in buckets.items()),
                      key=lambda p: (p["slides"] or [0])[0])

    floor = min(w for w, _ in options.values())
    k = min(k for k, (w, _) in options.items() if w <= floor + tolerance)
    groups = sorted(options[k][1],
                    key=lambda g: min(min(o.get("slides") or [0]) for o in g[1]))

    jokbo_ids = {c for c, _ in jokbo}
    parts, n_lec, n_jk = [], 0, 0
    for cids, objs, kind in groups:
        if cids[0] in jokbo_ids:
            n_jk += 1
            pid = f"jk{n_jk}"
        else:
            n_lec += 1
            pid = f"c{n_lec}"
        part = _part(pid, objs)
        part["topics"] = cids
        part["kind"] = kind
        parts.append(part)
    return parts


def _part(pid: str, objs: list[dict]) -> dict:
    slides = sorted({s for o in objs for s in (o.get("slides") or [])})
    targets = sum(_targets(o) for o in objs)
    return {
        "id": pid,
        "objectives": [str(o.get("id")) for o in objs],
        "slides": [slides[0], slides[-1]] if slides else None,
        "targets": targets,
        "cards": round(targets * TARGET_TO_CARD, 1),
        "occlusion": _has_occlusion(objs),
        "minutes": round(_cost(objs), 1),
    }


def plan(run_dir: Path, slots: int = DEFAULT_SLOTS,
         tolerance: float = TOLERANCE_MINUTES) -> dict:
    run_dir = Path(run_dir)
    structure = json.loads((run_dir / "structure.json").read_text(encoding="utf-8"))
    blueprint = json.loads((run_dir / "blueprint.json").read_text(encoding="utf-8"))

    buckets, orphans = assign_objectives(structure, blueprint)
    before = sorted((_part(cid, objs) for cid, objs in buckets.items()),
                    key=lambda p: (p["slides"] or [0])[0])
    after = rebalance(buckets, slots, tolerance)

    # 쪼개려 해도 objective 하나뿐이라 못 자른 큰 조각. 그것도 정보다 -
    # 그 자리는 0.5단계가 주제를 크게 잡았거나 청사진이 목표를 크게 세운 것이다.
    biggest = max((p["targets"] for p in after), default=0)
    stuck = [p for p in after
             if len(p["objectives"]) == 1 and p["targets"] >= biggest]

    return {
        "lecture_id": structure.get("lecture_id") or run_dir.name,
        "slots": slots, "tolerance": tolerance,
        "before": before, "after": after, "stuck": stuck,
        "orphans": [str(o.get("id")) for o in orphans],
        "wall_before": wall_clock(before, slots),
        "wall_after": wall_clock(after, slots),
        "work_before": sum(p["minutes"] for p in before),
        "work_after": sum(p["minutes"] for p in after),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="2단계 조각 배분 계산 (제안만 한다)")
    parser.add_argument("run_dir", help="runs/<lecture_id>")
    parser.add_argument("--slots", type=int, default=DEFAULT_SLOTS,
                        help=f"동시에 띄울 조각 수 (기본 {DEFAULT_SLOTS}. 실측으로 8은 확인됐다)")
    parser.add_argument("--tolerance", type=float, default=TOLERANCE_MINUTES,
                        help="벽시계가 이 안에서 같으면 조각을 적게 쓴다 "
                             f"(기본 {TOLERANCE_MINUTES}분)")
    parser.add_argument("--out", default="chunk_plan.json")
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    result = plan(run_dir, args.slots, args.tolerance)

    print(f"[plan] {result['lecture_id']} · 슬롯 {result['slots']}")
    print(f"{'조각':<7}{'슬라이드':>10}{'target':>8}{'카드':>7}{'소요':>8}"
          f" 가림  {'0.5단계 주제':<16} objective")
    for part in result["after"]:
        span = f"{part['slides'][0]}-{part['slides'][1]}" if part["slides"] else "-"
        objs = ", ".join(part["objectives"][:4])
        if len(part["objectives"]) > 4:
            objs += f" 외 {len(part['objectives']) - 4}"
        topics = "+".join(part.get("topics") or [])
        if part.get("kind") == "piece":
            topics += "의 일부"
        elif len(part.get("topics") or []) > 1:
            topics += " 합침"
        print(f"{part['id']:<7}{span:>10}{part['targets']:>8}{part['cards']:>7.1f}"
              f"{part['minutes']:>7.1f}분 {'●' if part['occlusion'] else ' ':<4} "
              f"{topics:<16} {objs}")

    if not any(p["occlusion"] for p in result["after"]):
        print("  (청사진에 `occlusion_candidate`가 하나도 없다 — 옛 청사진이거나 정말"
              " 없는 편이다.\n   있는데 표시가 없으면 예측이 조각당 4분씩 낙관적이다)")

    saved = result["wall_before"] - result["wall_after"]
    added = result["work_after"] - result["work_before"]
    print(f"\n  0.5단계 경계대로면 {len(result['before'])}조각 → 다시 담으면 "
          f"{len(result['after'])}조각")
    print(f"  예상 벽시계 {result['wall_before']:.1f}분 → {result['wall_after']:.1f}분"
          f"  ({'−' if saved >= 0 else '+'}{abs(saved):.1f}분)")
    print(f"  예상 작업합 {result['work_before']:.1f}분 → {result['work_after']:.1f}분"
          f"  ({'+' if added >= 0 else '−'}{abs(added):.1f}분 — 조각마다 "
          f"{FIXED_MINUTES}분 고정비가 붙는다)")

    if result["stuck"]:
        stuck = ", ".join(f"{p['id']}(target {p['targets']})" for p in result["stuck"])
        print(f"  ⚠ 가장 큰 조각이 objective 하나뿐이라 더 못 쪼갠다: {stuck}\n"
              "      벽시계가 여기서 막힌다. 줄이려면 0.5단계의 주제 경계나 "
              "청사진의 목표 크기를 봐라")
    if result["orphans"]:
        print(f"  ⚠ 어느 구간에도 안 드는 objective {len(result['orphans'])}개: "
              f"{', '.join(result['orphans'][:8])}")
    merged = [p for p in result["after"] if len(p.get("topics") or []) > 1]
    split = sorted({t for p in result["after"] if p.get("kind") == "piece"
                    for t in (p.get("topics") or [])})
    if merged:
        print("  주제를 합친 조각: "
              + ", ".join(f"{p['id']}({'+'.join(p['topics'])})" for p in merged))
    if split:
        print(f"  쪼갠 주제: {', '.join(split)}"
              " — 그 경계의 중복은 조각 안에서 안 잡힌다. 덱 감사가 받는다")
    if len(result["after"]) > result["slots"]:
        print(f"  ⚠ 조각 {len(result['after'])}개가 슬롯 {result['slots']}개를 넘는다 "
              "— 웨이브가 생겨 벽시계가 예상보다 는다")

    (run_dir / args.out).write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n  → {run_dir / args.out}  (제안이다. 쪼갠 자리가 말이 되는지는 네가 본다)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
