"""두 판의 `prep.json` 을 슬라이드 단위로 맞댄다. **무엇이 갈렸는지만 말한다.**

카드를 어떻게 할지는 여기서 정하지 않는다(`quizgen.revise`). 여기가 하는 일은 둘이다 —
v1 의 몇 번 슬라이드가 v2 의 몇 번인지 짝짓고, 짝지어진 슬라이드에서 **어느 채널이**
갈렸는지 세는 것.

## 번호로 맞대지 않는다

카드는 `slide_no` 정수 하나로 슬라이드에 묶인다. 슬라이드가 끼거나 빠지면 뒤가 통째로
밀리고, 밀린 채로 맞대면 **엉뚱한 카드를 지운다.** 그래서 본문 유사도로 먼저 짝짓는다.

**쪽수가 같다고 안심하지 않는다.** `260903_05` 는 v1·v2 가 둘 다 54쪽인데 필기가
갈린 판이었다. 쪽수·슬라이드 본문만 보면 「안 바뀌었다」가 나온다.

## 채널을 갈라서 센다

`lecture_text` 만 보면 필기만 갈린 판을 통째로 놓친다. 다섯 채널을 따로 세고, 무엇이
갈렸는지를 슬라이드마다 적는다.

**자리(rect)는 성기게 본다** — 5pt 로 반올림한다. 같은 주석을 조금 옮긴 것까지 「갈렸다」로
세면 재저장 한 번에 편 전체가 갈린 것이 된다. 반대로 **자리를 통째로 빼면 실제 수정을
놓친다.** `260903_05` 의 v1↔v2 가 그 예다 — 필기자가 슬라이드 1 에 *"p9 사진의 oral
sucker와 ventral sucker 라벨링이 반대로 되어있는 듯하여 수정했습니다"* 라고 적었고,
슬라이드 9 에서 그 두 라벨이 서로 자리를 바꿨다. 글자와 연도는 양쪽이 똑같아서
**자리를 안 보면 안 보이는 갈림**이다. 5pt 라는 눈금 자체는 아직 실측으로 고른 값이 아니다.

같은 쌍에서 이 모듈이 낸 값이 **54장 중 2장(4%)** 이다. 그때 통째 재빌드는 카드 53장 중
46장의 복습 이력을 버렸다.

사용:
    python -m quizgen.slidediff 옛/prep.json 새/prep.json
    python -m quizgen.slidediff 옛/prep.json 새/prep.json --slides 37 -o revise.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from difflib import SequenceMatcher
from pathlib import Path

# 짝으로 볼 최소 본문 유사도. 이 아래면 짝이 아니라 「빠졌다 + 새로 생겼다」로 본다.
PAIR_MIN_RATIO = 0.55
# 자리를 반올림할 눈금 (pt)
RECT_GRID = 5

CHANNELS = ("lecture_text", "lecture_figures", "lecture_emphasis",
            "annotations", "markers", "pasted_images", "occlusion_candidates")

# 채널마다 사람에게 하는 말. 「무엇이 갈렸는가」를 그대로 프롬프트에 싣는다.
CHANNEL_SAYS = {
    "lecture_text": "강의록 본문",
    "lecture_figures": "강의록 그림",
    "lecture_emphasis": "강의록이 색으로 강조한 곳",
    "annotations": "필기",
    "markers": "형광펜·밑줄·상자 같은 표시",
    "pasted_images": "필기자가 붙인 그림",
    "occlusion_candidates": "그림 위 라벨 (오클루전 후보)",
    # 채널이 아니다. 사람이 지목한 슬라이드에 붙는 표. 코드가 못 보는 갈림
    # (그림 픽셀이 바뀐 것 등)이 여기로 들어온다.
    "hinted": "사람이 알려준 수정",
}

_WS = re.compile(r"\s+")
# 그림·오클루전 id 는 `fig_p07_01` 처럼 **쪽 번호를 품는다.** 슬라이드가 밀리면 같은
# 그림도 id 가 달라지므로, 맞댈 때는 쪽 번호를 뗀 뒤 본다.
_ID_PAGE = re.compile(r"_p\d+_")


def norm(text: str) -> str:
    return _WS.sub(" ", (text or "")).strip()


def _grid(rect: list | None) -> tuple:
    if not rect:
        return ()
    return tuple(round(float(v) / RECT_GRID) for v in rect)


def _fig_key(f: dict) -> tuple:
    return (_ID_PAGE.sub("_p_", str(f.get("id") or "")), _grid(f.get("bbox")))


def projection(page: dict, channel: str):
    """맞댈 때 쓰는 채널의 알맹이. 순서와 미세한 자리는 뺀다."""
    if channel == "lecture_text":
        return norm(page.get("lecture_text", ""))
    if channel == "lecture_figures":
        return sorted(_fig_key(f) for f in page.get("lecture_figures") or [])
    if channel == "lecture_emphasis":
        return sorted((e.get("color", ""), norm(e.get("text", "")))
                      for e in page.get("lecture_emphasis") or [])
    if channel == "annotations":
        return sorted((a.get("year", ""), norm(a.get("text", "")), _grid(a.get("rect")))
                      for a in page.get("annotations") or [])
    if channel == "markers":
        return sorted((m.get("label") or m.get("kind", ""), m.get("year", ""),
                       _grid(m.get("rect")), tuple(norm(t) for t in m.get("covers") or []))
                      for m in page.get("markers") or [])
    if channel == "pasted_images":
        return sorted((p.get("year", ""), _grid(p.get("rect")))
                      for p in page.get("pasted_images") or [])
    if channel == "occlusion_candidates":
        return sorted((norm(o.get("label", "")),
                       _ID_PAGE.sub("_p_", str(o.get("figure_id") or "")))
                      for o in page.get("occlusion_candidates") or [])
    raise KeyError(channel)


def comparable(old_pages: list[dict], new_pages: list[dict]) -> tuple[list[str], list[str]]:
    """맞댈 수 있는 채널과 못 맞대는 채널.

    **한쪽 판에 그 채널이 통째로 없으면 자료가 아니라 코드가 달라진 것이다.**
    2026-09-03 에 `lecture_emphasis`(강의록이 색으로 강조한 곳)가 붙었는데, 그 전에
    만든 `prep.json` 에는 그 키가 아예 없다. 그대로 맞대면 **강의는 그대로인데
    5장이 갈렸다**고 나온다 — `260903_05` v1↔v2 를 실제로 대 보니 7장 중 5장이
    그 허깨비였다(남은 진짜는 필기 2장).

    키가 있고 값이 빈 것(`[]`)은 「그 슬라이드에 없다」이므로 정상 비교 대상이다.
    없는 것은 **키 자체가 한쪽 전 슬라이드에서 안 보이는 경우**뿐이다.
    """
    ok, skipped = [], []
    for channel in CHANNELS:
        in_old = any(channel in p for p in old_pages)
        in_new = any(channel in p for p in new_pages)
        (ok if in_old == in_new else skipped).append(channel)
    return ok, skipped


def align_key(page: dict) -> str:
    """짝짓기용 열쇠. 본문이 없는 슬라이드는 그림 생김새로 대신한다.

    래스터 슬라이드에는 텍스트 레이어가 아예 없다. 빈 문자열로 두면 그런 슬라이드가
    서로 전부 같아 보여 짝이 뒤섞인다.
    """
    text = norm(page.get("lecture_text", ""))
    if text:
        return text
    figs = projection(page, "lecture_figures")
    return "\x00fig:" + json.dumps(figs, ensure_ascii=False)


def _ratio(a: str, b: str) -> float:
    if a == b:
        return 1.0
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def align(old_pages: list[dict], new_pages: list[dict]) -> list[tuple[int | None, int | None]]:
    """(옛 슬라이드 번호, 새 슬라이드 번호). 한쪽이 없으면 None.

    같은 열쇠끼리 먼저 붙이고(`SequenceMatcher`), 남은 덩어리 안에서만 본문 유사도로
    짝을 찾는다. 유사도가 문턱 아래면 짝짓지 않는다 — **엉뚱하게 짝지어 놓고 「안
    바뀌었다」로 보는 것이 제일 나쁘다.**
    """
    a_keys = [align_key(p) for p in old_pages]
    b_keys = [align_key(p) for p in new_pages]
    out: list[tuple[int | None, int | None]] = []

    for tag, i1, i2, j1, j2 in SequenceMatcher(None, a_keys, b_keys).get_opcodes():
        if tag == "equal":
            out += [(old_pages[i]["slide"], new_pages[j]["slide"])
                    for i, j in zip(range(i1, i2), range(j1, j2), strict=True)]
            continue
        left, right = list(range(i1, i2)), list(range(j1, j2))
        taken: set[int] = set()
        spare: list[int] = []
        for i in left:
            best, score = None, PAIR_MIN_RATIO
            for j in right:
                if j in taken:
                    continue
                r = _ratio(a_keys[i], b_keys[j])
                if r >= score:
                    best, score = j, r
            if best is None:
                spare.append(i)
            else:
                taken.add(best)
                out.append((old_pages[i]["slide"], new_pages[best]["slide"]))

        # 남은 것은 **자리 순서로** 짝짓는다. 통째로 고쳐 쓴 슬라이드는 유사도가
        # 문턱 아래로 떨어지는데, 그것을 「빠졌다 + 새로 생겼다」로 적으면 사람이
        # 보고서에서 그 자리를 못 알아본다. 짝지어도 안전한 이유는 **짝지었다고
        # 그대로 옮기는 것이 아니기 때문**이다 — 채널이 하나도 안 갈린 짝만
        # 옮기고(유사도 1.0 이라 여기까지 오지 않는다), 갈린 짝의 카드는 모델이
        # 카드마다 처분을 정한다.
        rest = [j for j in right if j not in taken]
        for i, j in zip(spare, rest, strict=False):
            out.append((old_pages[i]["slide"], new_pages[j]["slide"]))
        out += [(old_pages[i]["slide"], None) for i in spare[len(rest):]]
        out += [(None, new_pages[j]["slide"]) for j in rest[len(spare):]]

    out.sort(key=lambda pr: (pr[1] if pr[1] is not None else 10 ** 6,
                             pr[0] if pr[0] is not None else 10 ** 6))
    return out


def diff(old: dict, new: dict, hints: list[int] | None = None) -> dict:
    """두 `prep.json` 을 맞댄다. `hints` 는 **사람이 알려준 새 판의 슬라이드 번호**다.

    사람이 「37p 를 고쳤다」고 하면 그 슬라이드는 무조건 바뀐 것으로 본다. 코드가
    못 보는 갈림이 있다 — 그림 픽셀이 바뀐 것은 어느 채널로도 안 잡힌다.
    """
    old_pages, new_pages = old["pages"], new["pages"]
    by_old = {p["slide"]: p for p in old_pages}
    by_new = {p["slide"]: p for p in new_pages}
    hinted = sorted({int(h) for h in (hints or [])})

    channels, skipped = comparable(old_pages, new_pages)
    pairs, added, removed = [], [], []
    carry: dict[str, int] = {}
    moved_to: dict[str, int] = {}
    for o, n in align(old_pages, new_pages):
        if o is None:
            added.append(n)
            continue
        if n is None:
            removed.append(o)
            continue
        changed = [c for c in channels
                   if projection(by_old[o], c) != projection(by_new[n], c)]
        if n in hinted:
            changed = changed + ["hinted"]
        row = {"old": o, "new": n, "changed": changed,
               "text_ratio": round(_ratio(norm(by_old[o].get("lecture_text", "")),
                                          norm(by_new[n].get("lecture_text", ""))), 3),
               "moved": o != n}
        pairs.append(row)
        moved_to[str(o)] = n
        if not changed:
            carry[str(o)] = n

    changed_slides = sorted([p["new"] for p in pairs if p["changed"]] + added)
    n_new = len(new_pages)
    return {
        "old": {"source": old.get("source"), "slides": old.get("slides"),
                "sha256": old.get("source_sha256", "")},
        "new": {"source": new.get("source"), "slides": new.get("slides"),
                "sha256": new.get("source_sha256", "")},
        "pairs": pairs,
        "added": added,
        "removed": removed,
        "moved": [p for p in pairs if p["moved"]],
        "hinted": hinted,
        # 사람이 알려줬는데 새 판에 그 번호가 없다. 조용히 삼키면 「고쳤다고 했는데
        # 그 슬라이드는 그대로」가 된다.
        "hinted_missing": [h for h in hinted if h not in by_new],
        # 카드를 다시 써야 하는 자리 (**새 판의 번호**)
        "changed_slides": changed_slides,
        # 옛 번호 → 새 번호. 여기 있는 슬라이드의 카드는 **모델을 안 거치고** 옮긴다.
        "carry_map": carry,
        # 짝지어진 모든 슬라이드의 옛 번호 → 새 번호. 갈린 슬라이드도 들어 있다 —
        # 그 자리의 카드도 번호는 밀어 줘야 하기 때문이다. 여기 없는 옛 번호는
        # 새 판에서 없어진 슬라이드다.
        "slide_map": moved_to,
        "ratio": round(len(changed_slides) / n_new, 3) if n_new else 1.0,
        "channel_counts": {c: sum(1 for p in pairs if c in p["changed"]) for c in CHANNELS},
        # 한쪽 판에만 있는 채널. 자료가 아니라 **prep 을 만든 코드가 달라진 것**이라
        # 맞대지 않았다. 못 본 갈림이 여기 숨어 있을 수 있다.
        "skipped_channels": skipped,
    }


def _text_hunks(a: str, b: str, pad: int = 34, limit: int = 6) -> list[str]:
    """본문에서 **갈린 덩어리만** 앞뒤 문맥과 함께 뽑는다.

    슬라이드 본문은 천 자가 넘는 것이 흔하다. 통째로 두 벌 실으면 프롬프트가
    부풀고, 정작 어디가 갈렸는지는 모델이 다시 찾아야 한다.
    """
    out = []
    for tag, i1, i2, j1, j2 in SequenceMatcher(None, a, b).get_opcodes():
        if tag == "equal":
            continue
        out.append(f"      v1: …{a[max(0, i1 - pad):i2 + pad]}…\n"
                   f"      v2: …{b[max(0, j1 - pad):j2 + pad]}…")
        if len(out) >= limit:
            out.append("      (그 밖에도 갈린 데가 있다)")
            break
    return out


def detail(old_page: dict, new_page: dict, changed: list[str], cap: int = 4) -> list[str]:
    """무엇이 어떻게 갈렸는지를 **문구로** 적는다.

    채널 이름만으로는 오타인지 내용 정정인지 알 수 없다 — `facificum → pacificum`
    과 `연충 → 원충` 은 글자로는 같은 크기인데 하나는 표기이고 하나는 뜻이다.
    그 판정은 이 목록을 보고 모델이 한다(`prompts/revise.md`).
    """
    lines = []
    for ch in changed:
        if ch == "hinted":
            lines.append("    · 사람이 이 슬라이드를 고쳤다고 알려줬다")
            continue
        say = CHANNEL_SAYS.get(ch, ch)
        if ch == "lecture_text":
            hunks = _text_hunks(norm(old_page.get("lecture_text", "")),
                                norm(new_page.get("lecture_text", "")))
            lines.append(f"    · {say}")
            lines += hunks
            continue
        before = {str(x): x for x in projection(old_page, ch)}
        after = {str(x): x for x in projection(new_page, ch)}
        gone = [before[k] for k in before if k not in after]
        came = [after[k] for k in after if k not in before]
        # **글자는 같은데 자리만 갈린 것**을 따로 뺀다. 그것도 진짜 갈림이다 —
        # `260903_05` 는 그림 위 라벨 두 개가 서로 자리를 바꾼 판이었다.
        gone_say = {_say_item(ch, x) for x in gone}
        shifted = [x for x in came if _say_item(ch, x) in gone_say]
        came = [x for x in came if _say_item(ch, x) not in gone_say]
        gone = [x for x in gone if _say_item(ch, x) not in {_say_item(ch, y) for y in shifted}]
        lines.append(f"    · {say} — 생김 {len(came)} · 없어짐 {len(gone)}"
                     + (f" · 글자는 그대로인데 자리가 갈림 {len(shifted)}" if shifted else ""))
        for x in came[:cap]:
            lines.append(f"      + {_say_item(ch, x)}")
        for x in gone[:cap]:
            lines.append(f"      - {_say_item(ch, x)}")
        for x in shifted[:cap]:
            lines.append(f"      ↔ {_say_item(ch, x)}")
    return lines


def _say_item(channel: str, item, width: int = 200) -> str:
    """자리(rect)는 안 보여 준다 — 사람도 모델도 그 숫자로는 판단하지 않는다.

    다만 **자리만 갈린 것**은 그렇다고 말해 줘야 한다. 형광펜이 다른 용어로 옮겨
    간 것이 그 꼴로 온다(`260903_05` 의 oral/ventral sucker 라벨이 그랬다).
    """
    if channel == "annotations":
        year, text, _rect = item
        return f"{year} 필기: {text[:width]}"
    if channel == "markers":
        kind, year, _rect, covers = item
        head = f"{year} {kind}"
        return f"{head} — 덮은 문구 {' / '.join(t[:80] for t in covers)}" if covers else f"{head} (덮은 문구 없음)"
    if channel == "lecture_emphasis":
        color, text = item
        return f"{color} {text[:width]}"
    return str(item)[:width]


def render(d: dict) -> str:
    """프롬프트와 사람 둘 다에게 보이는 요약."""
    L = [f"# 판 비교 — {d['old']['source']} → {d['new']['source']}", "",
         f"슬라이드 {d['old']['slides']}장 → {d['new']['slides']}장 · "
         f"바뀐 슬라이드 {len(d['changed_slides'])}장 ({d['ratio']:.0%})", ""]
    if d["hinted"]:
        L += [f"사람이 알려준 슬라이드: {d['hinted']}", ""]
    if d.get("skipped_channels"):
        L += ["⚠ 한쪽 판에만 있는 채널이라 맞대지 않았다 — "
              + ", ".join(CHANNEL_SAYS.get(c, c) for c in d["skipped_channels"])
              + ". 그 판을 만든 prep 코드가 다르다는 뜻이고, "
              "여기 숨은 갈림은 못 본다.", ""]
    if d["hinted_missing"]:
        L += [f"⚠ 알려준 슬라이드 중 새 판에 없는 번호: {d['hinted_missing']} "
              f"(새 판은 {d['new']['slides']}장이다)", ""]
    if d["added"]:
        L.append(f"- 새로 생긴 슬라이드: {d['added']}")
    if d["removed"]:
        L.append(f"- 없어진 슬라이드(옛 번호): {d['removed']}")
    if d["moved"]:
        L.append("- 번호가 밀린 슬라이드: "
                 + ", ".join(f"{p['old']}→{p['new']}" for p in d["moved"][:20]))
    L.append("")
    L.append("## 바뀐 슬라이드")
    L.append("")
    for p in d["pairs"]:
        if not p["changed"]:
            continue
        what = ", ".join(CHANNEL_SAYS.get(c, c) for c in p["changed"])
        old_no = f" (옛 {p['old']})" if p["moved"] else ""
        L.append(f"- **Slide {p['new']}**{old_no} — {what}"
                 + (f" · 본문 유사도 {p['text_ratio']:.2f}" if "lecture_text" in p["changed"] else ""))
    for n in d["added"]:
        L.append(f"- **Slide {n}** — 새로 생긴 슬라이드")
    L.append("")
    return "\n".join(L)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="두 판의 prep.json 을 슬라이드 단위로 맞댄다")
    ap.add_argument("old", help="옛 판의 prep.json")
    ap.add_argument("new", help="새 판의 prep.json")
    ap.add_argument("--slides", default="",
                    help="사람이 알려준 새 판의 슬라이드 번호 (쉼표 구분). "
                         "코드가 못 보는 갈림을 여기에 넣는다")
    ap.add_argument("-o", "--out", help="결과 json 을 쓸 자리")
    args = ap.parse_args(argv)

    old = json.loads(Path(args.old).read_text(encoding="utf-8"))
    new = json.loads(Path(args.new).read_text(encoding="utf-8"))
    hints = [int(x) for x in args.slides.replace(" ", "").split(",") if x]
    d = diff(old, new, hints)
    print(render(d))
    print("채널별 갈린 슬라이드 수: "
          + ", ".join(f"{CHANNEL_SAYS[c]} {n}" for c, n in d["channel_counts"].items() if n))
    if args.out:
        Path(args.out).write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n→ {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
