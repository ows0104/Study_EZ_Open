"""오클루전 패스 — 그림의 라벨을 가린 카드를 만든다 (인터뷰 ㉙~㉟).

    python -m quiz2.occlusion plan runs/260819_01      # → spawn/occl.bNN.md
    #  배치마다 서브에이전트를 하나씩. 각자 아래 render를 돌려 가며 고친다
    python -m quiz2.occlusion render runs/260819_01 --items items.raw.occl_b01.json

## 왜 별도 패스인가

**단발 호출로 안 되는 유일한 작업이다.** 상자를 그려 렌더하고 라벨을 덜 덮었는지
눈으로 봐야 하므로 한 번에 안 끝난다. 인터뷰에서 그걸 알고 골랐다(⑳″).

1회차에서 **한 장도 안 나왔다.** `prompt.py`에 `OCCLUSION` 규칙 문자열이 있는데
`make_prompt`가 그걸 어디에도 안 넣는다 — 규칙만 있고 부르는 자리가 없었다.

## 코드가 잡아 주는 것 두 가지

`CLAUDE.md`가 감사의 한계를 이렇게 적어 두었다 — 오클루전 결함 셋 중 *"상자가
라벨을 덜 덮은 것은 셋 중 하나만, 가린 답이 아래 행에 그대로 있던 것은 아무도
온전히 못 잡았다."* 둘 다 **좌표와 문자열로 셀 수 있다.**

    answer_text_elsewhere      가린 라벨의 글자가 슬라이드의 **안 가린 다른 라벨**에
                               그대로 또 있다. ㉝의 자리다 — 카드를 버리지 말고
                               그 자리를 `mask_label_ids`로 같이 덮으면 된다
    answer_text_in_annotation  가린 라벨의 글자가 그 슬라이드 **필기**에 또 있다 (㉞)
    rect_clips_label           직접 적은 좌표가 라벨을 **걸치기만 하고 다 못 덮었다.**
                               글자 끝이 삐져나오면 정답이 새어 보인다

세는 것까지가 코드다. 지울지 고칠지는 언제나 사람과 모델이 정한다(CLAUDE.md).

## 채널은 필기본이다 (㉞)

v1은 필기를 지운 `model_input.pdf`에 그렸다. 관리자가 필기본으로 바꿨다.
**알고 있는 위험**은 필기에 답이 적혀 있으면 가려도 그 필기가 답을 보여 준다는
것이었다. 첫 렌더에서 바로 나왔다 — s13에서 인쇄된 `(beta globin)`을 덮었는데
하단 필기가 `beta-globin allele 건드리는 혈액질환`이라고 적고 있었다.

그래서 `annotations.json`의 `notes`를 같은 잣대로 함께 센다. `260819_01`의 후보
슬라이드에서 라벨 267개 중 **7개**가 그 슬라이드 필기에 글자로 또 있었다.

**못 세는 것이 남는다** — 필기가 답을 바꿔 말하거나(`같은 유전자의 결과이다`),
글자가 아니라 그림으로 그려져 있으면 이 검사가 못 본다. 그건 눈이 유일한 장치다.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass

from quiz.occlusion import (  # noqa: E402
    build_label_index,
    render_occlusion_pair,
    resolve_rects,
)
from quiz.textutil import safe_filename, safe_media_prefix  # noqa: E402
from quiz import timings  # noqa: E402
from quiz2 import prompt as prompt_mod  # noqa: E402


# 후보를 좁히는 조건. **한도가 아니라 추림이다** — 목록에 있어도 안 만들어도 되고,
# 라벨이 안 잡힌 그림은 정규화 좌표로 직접 적으면 된다(㉚ "회수 목표가 있는 것만").
MIN_LABELS = 2
MIN_IMAGE_RATIO = 0.2

# 배치 하나가 맡는 후보 슬라이드 수. 렌더-확인-수정을 슬라이드마다 도는 자리라
# 한 배치를 크게 잡으면 문맥이 길어진다. `reproduce.py`와 같은 이유의 값이다.
BATCH_SIZE = 5

# 각인 라벨. 모든 슬라이드에 하나씩 있고 가릴 이유가 없다.
_STAMP_RE = re.compile(r"^Slide\s+\d+$")

# 누출 비교용. **낱말 배열로 잰다.** 뭉갠 문자열로 재면 오탐이 섞인다 —
# `260819_01`에서 실제로 `Male` ⊂ `Female`, `1 in 250` ⊂ `1 in 25,000`이 걸렸다.
# 낱말로 끊으면 둘 다 안 걸리고, v1에서 실제로 샌 것(캡션 `Disuse atrophy`가 바로
# 아래 URL `.../disuse-atrophy`에 그대로 있던 것)은 그대로 걸린다.
_TOKEN_RE = re.compile(r"[0-9]+|[a-z]+|[가-힣]+")

# 이보다 짧은 라벨은 누출 검사에서 뺀다. `Yes`·`No` 같은 것이 슬라이드 곳곳에 있어
# 전부 걸리면 신호가 죽는다.
LEAK_MIN_CHARS = 4


def _text(value) -> str:
    return str(value or "").strip()


def _tokens(value: str) -> list[str]:
    return _TOKEN_RE.findall(str(value or "").lower())


def _contains_tokens(haystack: list[str], needle: list[str]) -> bool:
    """`needle`이 `haystack`에 **낱말 단위로 이어서** 들어 있나."""
    if not needle or len(needle) > len(haystack):
        return False
    return any(haystack[i:i + len(needle)] == needle
               for i in range(len(haystack) - len(needle) + 1))


def load_labels(run_dir: Path, prep: dict) -> dict[str, list[dict]]:
    path = run_dir / "labels.json"
    if not path.exists():
        path = Path(_text(prep.get("labels_path")))
    if not path.exists():
        raise SystemExit(f"labels.json이 없다: {run_dir}. prep.py를 먼저 돌려라")
    return json.loads(path.read_text(encoding="utf-8")).get("slides") or {}


def slide_labels(labels: dict, slide_no: int) -> list[dict]:
    """각인 라벨을 뺀 그 슬라이드의 라벨 후보."""
    return [e for e in labels.get(str(int(slide_no)), [])
            if not _STAMP_RE.match(_text(e.get("text")))]


def existing_items(run_dir: Path) -> list[dict]:
    """1단계가 낸 카드. 합치기 전이라 조각 파일에서 직접 읽는다.

    이 패스는 **1단계 뒤, merge 앞**에 선다 — 어느 슬라이드에 회수 목표가 있었는지는
    이미 나온 카드가 말해 주고(㉚), 결과는 `items.raw.occl_bNN.json`으로 떨어져
    merge가 나머지와 함께 주워 간다.
    """
    items: list[dict] = []
    for path in sorted(run_dir.glob("items.raw.*.json")):
        if path.name == "items.raw.json" or ".occl" in path.name:
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        items.extend(payload.get("cards") or payload.get("items") or [])
    return items


def candidates(run_dir: str | Path) -> list[dict]:
    """오클루전을 시도해 볼 만한 슬라이드. **추림이지 한도가 아니다.**

    조건 둘을 `or`로 묶는다.

    - 1단계가 그 슬라이드의 **그림이나 표를 근거로 카드를 냈다** (`evidence_type`).
      회수 목표가 이미 확인된 자리다
    - 페이지에서 그림이 차지하는 비율이 높다

    `or`인 이유가 실측에 있다 — `260819_01`에서 `image_ratio`가 0인 슬라이드가
    67장 중 45장인데, 그중에도 `figure` 근거 카드가 있는 슬라이드가 있었다(s9의
    Mutation 도식). 벡터로 그린 도식은 래스터 이미지가 아니라 비율이 0으로 잡힌다.
    비율만 보면 그런 그림을 통째로 놓친다.
    """
    run_dir = Path(run_dir)
    prep = json.loads((run_dir / "prep.json").read_text(encoding="utf-8"))
    structure = json.loads((run_dir / "structure.json").read_text(encoding="utf-8"))
    labels = load_labels(run_dir, prep)
    features = {f["slide_no"]: f for f in json.loads(
        (run_dir / "page_features.json").read_text(encoding="utf-8"))}
    items = existing_items(run_dir)

    figure_slides = {int(i["slide_no"]) for i in items
                     if _text(i.get("evidence_type")) in ("figure", "table")
                     and _text(i.get("slide_no"))}
    carded = {int(i["slide_no"]) for i in items if _text(i.get("slide_no"))}

    lo, hi = (int(structure["lecture_range"][0]), int(structure["lecture_range"][1]))
    rows: list[dict] = []
    for slide_no in range(lo, hi + 1):
        entries = slide_labels(labels, slide_no)
        if len(entries) < MIN_LABELS:
            continue
        ratio = float(features.get(slide_no, {}).get("image_ratio") or 0.0)
        has_figure = slide_no in figure_slides
        if not has_figure and ratio < MIN_IMAGE_RATIO:
            continue
        rows.append({
            "slide_no": slide_no,
            "image_ratio": round(ratio, 2),
            "figure_card": has_figure,
            "carded": slide_no in carded,
            "labels": entries,
        })
    return rows


# ── 코드가 잡아 주는 결함 ──────────────────────────────────────────────

def _overlaps(a: list[float], b: list[float]) -> bool:
    return not (a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1])


def _contains(outer: list[float], inner: list[float]) -> bool:
    return (outer[0] <= inner[0] and outer[1] <= inner[1]
            and outer[2] >= inner[2] and outer[3] >= inner[3])


def check_card(item: dict, labels: dict, notes: dict | None = None) -> list[str]:
    """가린 뒤에도 답이 보이는가. **좌표와 문자열로 셀 수 있는 것만 본다.**

    감사가 못 잡았다고 기록된 것들이다(`CLAUDE.md`). 세기만 하고 판정하지 않는다.

    `notes`는 `{슬라이드번호: [필기 문자열]}`. ㉞이 경고한 자리를 여기서 센다.
    """
    occlusion = item.get("occlusion") or {}
    slide_no = int(item.get("slide_no") or 0)
    entries = slide_labels(labels, slide_no)
    by_id = {e["id"]: e for e in entries if e.get("id")}
    problems: list[str] = []

    answer_ids = [str(i) for i in (occlusion.get("label_ids") or [])]
    mask_ids = [str(i) for i in (occlusion.get("mask_label_ids") or [])]
    covered = set(answer_ids) | set(mask_ids)

    # ① ㉝ — 가린 답이 슬라이드 다른 자리에 글자로 그대로 있다.
    for lid in answer_ids:
        entry = by_id.get(lid)
        if not entry:
            continue
        needle = _tokens(entry.get("text"))
        if sum(len(t) for t in needle) < LEAK_MIN_CHARS:
            continue
        for other in entries:
            if other.get("id") in covered or other.get("id") == lid:
                continue
            hay = _tokens(other.get("text"))
            if _contains_tokens(hay, needle) or _contains_tokens(needle, hay):
                problems.append(
                    f"answer_text_elsewhere({lid} '{_text(entry.get('text'))[:24]}'"
                    f" → {other.get('id')} '{_text(other.get('text'))[:24]}')")
                break

    # ② ㉞ — 가린 답이 그 슬라이드 필기에 글자로 또 있다.
    note_tokens = _tokens(" ".join((notes or {}).get(slide_no) or []))
    if note_tokens:
        for lid in answer_ids:
            entry = by_id.get(lid)
            if not entry:
                continue
            needle = _tokens(entry.get("text"))
            if sum(len(t) for t in needle) < LEAK_MIN_CHARS:
                continue
            if _contains_tokens(note_tokens, needle):
                problems.append(
                    f"answer_text_in_annotation({lid} "
                    f"'{_text(entry.get('text'))[:24]}')")

    # ③ 직접 적은 좌표가 라벨을 걸치기만 하고 다 못 덮었다.
    for key in ("rects", "mask_rects"):
        for raw in occlusion.get(key) or []:
            try:
                rect = [float(v) for v in raw]
            except (TypeError, ValueError):
                continue
            for entry in entries:
                label_rect = entry.get("rect")
                if not label_rect:
                    continue
                if _overlaps(rect, label_rect) and not _contains(rect, label_rect):
                    problems.append(
                        f"rect_clips_label({key} {rect} ⊅ {entry.get('id')}"
                        f" '{_text(entry.get('text'))[:24]}')")
    return problems


# ── 렌더 ───────────────────────────────────────────────────────────────

def render(run_dir: str | Path, items_name: str) -> dict:
    """오클루전 카드마다 앞/뒤 PNG를 뽑고, 기계가 볼 수 있는 것을 함께 센다."""
    run_dir = Path(run_dir)
    prep = json.loads((run_dir / "prep.json").read_text(encoding="utf-8"))
    labels = load_labels(run_dir, prep)
    label_index = build_label_index({"slides": labels})

    notes_file = run_dir / "annotations.json"
    notes: dict[int, list[str]] = {}
    if notes_file.exists():
        for entry in json.loads(notes_file.read_text(encoding="utf-8")):
            notes[int(entry.get("slide_no") or 0)] = entry.get("notes") or []

    payload = json.loads((run_dir / items_name).read_text(encoding="utf-8"))
    items = payload.get("cards") or payload.get("items") or []
    targets = [i for i in items if i.get("occlusion")]

    # ㉞ 필기본에 그린다. v1은 필기를 지운 채널이었다.
    source = prep.get("annotated_pdf") or prep.get("source_pdf")
    out_dir = run_dir / "occl_preview"
    prefix = safe_media_prefix(prep["source_stem"])

    rows: list[dict] = []
    for index, item in enumerate(targets):
        slide_no = int(item.get("slide_no") or 0)
        rects, masks, problems = resolve_rects(
            item.get("occlusion") or {}, slide_no, label_index)
        # merge가 붙이기 전이라 `id`가 없다. 파일 이름이 질문 앞머리가 되면
        # 길고 편마다 달라지므로 자리 번호로 대신한다.
        row = {
            "id": _text(item.get("id")) or f"n{index + 1:02d}",
            "slide_no": slide_no,
            "boxes": len(rects),
            "masks": len(masks),
            "problems": problems + check_card(item, labels, notes),
        }
        if rects:
            basename = f"{prefix}_occl_s{slide_no:03d}_{safe_filename(str(row['id']))}"
            front, back = render_occlusion_pair(
                source, slide_no, rects, out_dir, basename,
                band_pt=float(prep.get("stamp_band_pt") or 0.0), masks=masks)
            row["front"] = str(out_dir / front)
            row["back"] = str(out_dir / back)
        rows.append(row)

    return {"items": len(items), "occlusion": len(targets), "out_dir": str(out_dir),
            "source": str(source), "cards": rows,
            "flagged": sum(1 for r in rows if r["problems"])}


# ── 스폰 문구 ──────────────────────────────────────────────────────────

DO_NOT = """\
## 하지 말 것

- **1단계가 만든 카드 파일을 열지 마라.** 겹치는지는 아래 「이미 나온 카드」를 보면 된다
- **`labels.json`을 열지 마라.** 네 후보 슬라이드의 라벨은 전부 아래 표에 있다
- **`quiz/occlusion.py`나 `validate.py`를 읽거나 돌리지 마라.**
  좌표를 푸는 것도 그리는 것도 아래 `render` 한 줄이 한다
- **후보를 다 쓰려고 하지 마라.** 회수 목표가 없는 그림은 그냥 넘긴다 (㉚)
"""


def _label_table(row: dict) -> str:
    lines = [f"### 슬라이드 {row['slide_no']}"
             f"  (그림 비율 {row['image_ratio']}"
             + (", 1단계가 그림·표를 근거로 카드를 냈다" if row["figure_card"] else "")
             + ")",
             "",
             "| label_id | 글자 |", "|---|---|"]
    for e in row["labels"]:
        lines.append(f"| `{e['id']}` | {_text(e.get('text')).replace('|', '/')} |")
    return "\n".join(lines)


def spawn_prompt(run_dir: Path, rows: list[dict], batch: str, out_path: Path,
                 nearby: list[dict]) -> str:
    parts = [
        f"# 오클루전 패스 `{batch}` — 슬라이드 "
        + ", ".join(str(r["slide_no"]) for r in rows),
        ("그림의 라벨을 가린 앞면과 드러낸 뒷면이 붙는 카드를 만든다.\n\n"
         "**이 작업만 한 번에 안 끝난다.** 상자를 고르고, 렌더해서, 라벨을 덜 덮었는지 "
         "눈으로 보고, 고친다. 아래 「돌리는 법」이 그 고리다."),
        prompt_mod.OCCLUSION,
        "## 네가 맡은 후보\n\n"
        "1단계가 그림·표를 근거로 카드를 냈거나 그림 비율이 높은 슬라이드다. "
        "**추림이지 한도가 아니다** — 회수 목표가 없으면 넘기고, 라벨이 안 잡힌 "
        "그림은 정규화 좌표(0~1)로 직접 적어도 된다.\n\n"
        + "\n\n".join(_label_table(r) for r in rows),
    ]

    if nearby:
        lines = ["## 이미 나온 카드 (겹치지 마라)", "",
                 "1단계가 이 슬라이드들에서 낸 카드다. 같은 것을 그림으로 다시 묻는 것은 "
                 "중복이 아니지만(회수 방향이 다르다), **같은 회수 방향을 두 번 내지는 "
                 "마라.**", ""]
        for i in nearby:
            lines.append(f"- s{i.get('slide_no')} · {_text(i.get('q'))[:70]}")
        parts.append("\n".join(lines))

    parts.append(f"""\
## 돌리는 법

1. 상자를 고르고 아래 꼴로 `{out_path}`에 쓴다
2. 렌더한다

       python -m quiz2.occlusion render {run_dir} --items {out_path.name}

3. 나온 앞면 PNG를 `Read`로 **직접 본다.** 확인할 것은 셋이다
   - 가려야 할 글자가 상자 밖으로 삐져나오지 않았나
   - 가리지 말아야 할 것까지 덮지 않았나
   - 답이 슬라이드 다른 자리에 그대로 보이지 않나 (필기도 포함이다)
4. 어긋났으면 고쳐 쓰고 2로 돌아간다. **여기서는 고쳐 쓰는 것이 정상이다** —
   다른 패스와 다른 점이다

렌더가 두 가지를 대신 세어 준다. 감사가 못 잡던 자리다.

    answer_text_elsewhere      가린 답이 안 가린 다른 라벨에 글자로 또 있다
                               → 버리지 말고 그 자리를 `mask_label_ids`로 덮어라
    answer_text_in_annotation  가린 답이 그 슬라이드 **필기**에 글자로 또 있다
    rect_clips_label           직접 적은 좌표가 라벨을 걸치기만 하고 다 못 덮었다

**세어 주는 것은 여기까지다.** 필기가 답을 **바꿔 말하거나**(`같은 유전자의
결과이다`) 글자가 아니라 **그림으로** 그려져 있으면 코드가 못 본다.
그건 3번에서 네 눈이 유일한 장치다.""")

    parts.append(DO_NOT)
    parts.append(f"""\
## 출력

`{out_path}`에 JSON 하나로 쓴다.

```json
{{
  "cards": [
    {{"q": "A로 표시된 구조의 이름은?", "a": "...", "explanation": "...",
     "slide_no": 13, "card_type": "fact", "card_format": "basic",
     "importance": "core", "exam_hit": false,
     "evidence_type": "figure", "source_type": "lecture",
     "occlusion": {{"label_ids": ["s013_l01"],
                   "mask_label_ids": ["s013_l07"],
                   "rects": [], "mask_rects": []}}}}
  ]
}}
```

- `label_ids`가 **답 상자**다. 앞면에 `A`·`B`… 표식이 붙고 학습자가 그 수만큼 회수한다
- `mask_label_ids`는 **표식이 안 붙는 덮개**다. 답이 딴 데 적힌 자리를 덮는 데 쓴다.
  회수 대상이 아니므로 개수에 안 센다 (㉝)
- 라벨이 안 잡힌 그림은 `rects`/`mask_rects`에 `[x0, y0, x1, y1]`을 0~1로 적는다
- 답 상자가 하나도 없으면 물을 것이 없다. 그런 카드는 쓰지 마라""")
    return "\n\n".join(p.strip() for p in parts if p and p.strip())


def plan(run_dir: str | Path, batch_size: int = BATCH_SIZE) -> dict:
    run_dir = Path(run_dir)
    rows = candidates(run_dir)
    items = existing_items(run_dir)
    out_dir = run_dir / "spawn"
    out_dir.mkdir(parents=True, exist_ok=True)

    made: list[dict] = []
    for index in range(0, len(rows), batch_size):
        group = rows[index:index + batch_size]
        batch = f"b{index // batch_size + 1:02d}"
        out_path = run_dir / f"items.raw.occl_{batch}.json"
        slides = {r["slide_no"] for r in group}
        nearby = [i for i in items
                  if _text(i.get("slide_no")) and int(i["slide_no"]) in slides]
        text = spawn_prompt(run_dir, group, batch, out_path, nearby)
        spawn_file = out_dir / f"occl.{batch}.md"
        spawn_file.write_text(text, encoding="utf-8")
        made.append({
            "batch": batch,
            "slides": sorted(slides),
            "labels": sum(len(r["labels"]) for r in group),
            "spawn": str(spawn_file),
            "out": str(out_path),
            "chars": len(text),
        })
    return {"candidates": len(rows), "batches": made}


def main() -> int:
    parser = argparse.ArgumentParser(description="오클루전 패스 (인터뷰 ㉙~㉟)")
    parser.add_argument("stage", choices=["plan", "render"])
    parser.add_argument("run_dir")
    parser.add_argument("--items", default=None,
                        help="render: 렌더할 파일명 (예: items.raw.occl_b01.json)")
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE)
    args = parser.parse_args()
    run_dir = Path(args.run_dir)

    if args.stage == "plan":
        with timings.stage(run_dir, "3.5-occl-plan"):
            result = plan(run_dir, args.batch_size)
        if not result["candidates"]:
            print("[occlusion/plan] 후보 슬라이드가 없다. "
                  "라벨이 잡힌 그림 슬라이드가 없거나 1단계가 아직 안 돌았다")
            return 0
        print(f"[occlusion/plan] 후보 {result['candidates']}장 → "
              f"배치 {len(result['batches'])}개")
        for b in result["batches"]:
            print(f"  {b['batch']}  슬라이드 {b['slides']}  라벨 {b['labels']}개  "
                  f"{b['spawn']}")
        print("\n배치마다 서브에이전트를 하나씩. 각자 render를 돌려 가며 고친다.")
        print("띄우기 직전·받은 직후에 찍어라 — 렌더 반복이 여기 다 들어간다:")
        print(f"    python -m quiz2.timings {run_dir} start 3.5-occlusion --label b01")
        print(f"    python -m quiz2.timings {run_dir} end   3.5-occlusion --label b01")
        return 0

    if not args.items:
        print("[occlusion/render] --items 를 줘라 (예: items.raw.occl_b01.json)")
        return 2
    result = render(run_dir, args.items)
    print(f"[occlusion/render] 카드 {result['items']}장 중 오클루전 "
          f"{result['occlusion']}장  (채널: {result['source']})")
    for row in result["cards"]:
        print(f"\n  {row['id']}  s{row['slide_no']}  "
              f"상자 {row['boxes']} · 마스크 {row['masks']}")
        if row.get("front"):
            print(f"    앞면 {row['front']}")
            print(f"    뒷면 {row['back']}")
        for problem in row["problems"]:
            print(f"    ✗ {problem}")
    if result["occlusion"]:
        print(f"\n  표시된 카드 {result['flagged']}장 / {result['occlusion']}장")
        print("  **앞면 PNG를 직접 열어 봐라.** 필기가 답을 바꿔 말하거나 "
              "그림으로 그려져 있으면 코드가 못 센다")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
