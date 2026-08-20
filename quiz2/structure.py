"""0.5단계: `structure.json`을 쓸 서브에이전트에게 줄 문구를 조립한다.

    python -m quiz2.structure runs/260819_01     # → spawn/structure.md
    #  서브에이전트 하나에게 그 파일을 읽고 그대로 따르라고만 시킨다
    python quiz/structure.py runs/260819_01      # 쓴 것을 검증 (v1 코드 그대로)

## 왜 코드가 쓰지 않는가

*"이 페이지가 기출문제인가"*는 의미 판단이다. 정규식으로 문구를 찾던 이전 구현이
실물에서 깨졌다 — `260813_03`은 표지 문구가 "정답"이라 못 잡았고, p34에 "족보"가
있는데도 페이지 앞부분만 읽어서 놓쳤다 (`quiz/structure.py`).

주제 덩어리는 더 그렇다. 슬라이드 47과 48 사이가 경계인지는 세어서 안 나온다.

## 그런데 왜 지금까지 사람이 썼는가

**자리가 없었을 뿐이다.** v2는 1단계(조각별 카드)에만 스폰 문구가 있었고, 그 앞의
0.5단계는 `quiz/structure.py`의 **검증기만** 있고 판정하는 쪽이 비어 있었다.
이 모듈이 그 자리다.

## 이 문구가 없애려는 것

`assemble.py`와 같은 목적이다 — **찾을 것을 안 남기면 도구 호출이 0이 된다.**
0.5단계가 판정에 쓸 근거는 이미 전부 `prep.py`가 뽑아 두었다.

    outline.json       슬라이드마다 제목과 첫 줄. 주제 경계는 여기서 보인다
    page_features.json 글자수·필기수·답안나열·족보낱말·그림비율. 족보 경계는 여기서
    jokbo_text.md      외부 족보 원문 (있으면). exam_focus는 여기서

셋을 문구에 그대로 박아 넣는다. **남는 읽기는 하나뿐이다** — 필기 꼬리 족보는
캡처 이미지라 글자가 안 잡히므로(`260819_01`에서 s68~76이 21~52자였다) 그 구간만
`pages`로 눈으로 본다.

## exam_focus가 여기 있는 이유

경계를 찾느라 족보를 어차피 전부 읽는 자리다. v1은 그 읽기를 버리고 1단계 조각
아홉이 같은 쪽을 아홉 번 다시 읽었다. 인터뷰에서 0.5단계로 옮겼다.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass

from quiz.structure import PageFeature, scan_jokbo_start  # noqa: E402
from quiz import timings  # noqa: E402


# 제목은 통째로, 머리글은 잘라서. 머리글은 경계를 가리키는 데만 쓰므로 앞부분이면
# 충분하고, 전문을 실으면 한 편에 1만 자가 넘는다.
HEAD_MAX = 110

# 조각 하나의 최대 슬라이드 수. **하네스의 Read 상한이 20쪽이다.**
# 조각 PDF를 `pages` 없이 통째로 읽어야 텍스트 레이어가 따라오는데(`chunks.py`),
# 20쪽을 넘기면 그 읽기가 거부되어 1단계가 그림만 보게 된다.
CHUNK_SLIDES_MAX = 20

# 실측 범위. `260819_01` 9조각이 5~14장이었다. 한도가 아니라 관찰이다.
CHUNK_SLIDES_TYPICAL = "5~14"


DO_NOT = """\
## 하지 말 것

근거는 **전부 이 문구 안에 있다.** 아래 하나를 빼고는 찾으러 가지 마라.

- **`outline.json`·`page_features.json`을 열지 마라.** 표로 아래에 실려 있다
- **강의록 본문을 통독하지 마라.** 주제 경계는 제목 줄로 보인다.
  본문이 필요한 것은 카드를 만드는 1단계의 몫이고, 여기는 경계만 정한다
- **`quiz/structure.py`를 읽거나 돌리지 마라.** 검증은 네가 쓴 뒤에 코드가 한다.
  검증기가 무엇을 보는지는 아래 「검증기가 따지는 것」에 전부 옮겨 놓았다
- **쓴 뒤에 고쳐 쓰지 마라.** 한 번에 완성해서 한 번만 써라
"""


def _text(value) -> str:
    return str(value or "").strip()


def load_features(run_dir: Path, prep: dict) -> list[PageFeature]:
    path = run_dir / "page_features.json"
    if path.exists():
        return [PageFeature(**f) for f in json.loads(path.read_text(encoding="utf-8"))]
    raise SystemExit(f"{path}가 없다. prep.py를 먼저 돌려라")


def outline_table(run_dir: Path, prep: dict) -> str:
    """슬라이드마다 제목 한 줄. **주제 경계는 여기서 보인다.**

    `260819_01`에서는 족보 경계까지 여기서 보였다 — s68의 제목이
    `2022년 족보 - 강경훈 교수님 출제`였다. 늘 그렇지는 않으므로
    (`260813_03`은 표지 문구가 "정답"이었다) 수치 표와 함께 본다.
    """
    # `prep["outline_path"]`는 저장소 뿌리 기준 상대경로라 다른 데서 부르면
    # 못 찾는다. run_dir 안을 먼저 본다.
    path = run_dir / "outline.json"
    if not path.exists():
        path = Path(_text(prep.get("outline_path")))
    if not path.exists():
        return "## 슬라이드 제목\n\n`outline.json`이 없다. 원본을 직접 봐야 한다."

    entries = json.loads(path.read_text(encoding="utf-8"))
    lines = ["| # | 제목 | 첫 줄 |", "|---|---|---|"]
    for e in entries:
        title = _text(e.get("title")).replace("|", "/")
        head = _text(e.get("head")).replace("|", "/")
        if len(head) > HEAD_MAX:
            head = head[:HEAD_MAX] + "…"
        lines.append(f"| {e.get('slide_no')} | {title} | {head} |")
    return ("## 슬라이드 제목과 첫 줄\n\n"
            "주제 덩어리를 가르는 근거는 이 표다.\n\n" + "\n".join(lines))


def feature_table(features: list[PageFeature]) -> str:
    """기계가 센 것. **족보 경계는 여기서 보인다.**"""
    lines = [
        "## 슬라이드마다 기계가 센 것",
        "",
        "    글자    인쇄된 텍스트 글자수. 족보 캡처는 이 값이 낮다",
        "    필기    주석(annotation) 개수",
        "    답안    `12. 3` 꼴의 답안 나열 줄 수. **강의록에는 없다**",
        "    족보말  족보·기출·정답·기말 같은 낱말이 나온 횟수",
        "    그림    페이지에서 그림이 차지하는 넓이 비율",
        "",
        "| # | 글자 | 필기 | 답안 | 족보말 | 그림 |",
        "|---|---|---|---|---|---|",
    ]
    for f in features:
        lines.append(f"| {f.slide_no} | {f.chars} | {f.annots} | {f.answer_rows} "
                     f"| {f.jokbo_words} | {f.image_ratio:.2f} |")
    return "\n".join(lines)


def machine_hint(features: list[PageFeature], prep: dict) -> str:
    """기계의 짐작. **판정이 아니다 — 어긋나면 네가 이기고, 근거를 적어라.**"""
    total = len(features)
    scanned = scan_jokbo_start(features)
    lines = ["## 기계의 짐작 (판정이 아니다)", ""]
    if scanned is None:
        lines.append("정규식 스캐너는 **족보 꼬리를 못 찾았다.** 없을 수도 있고, "
                     "문구가 낯설어 놓쳤을 수도 있다. 위 두 표로 직접 가려라.")
    else:
        lines.append(f"정규식 스캐너는 기출 근거가 **필기 {scanned}쪽부터** 이어진다고 센다.")
        lines.append("")
        lines.append("이건 뒤에서부터 답안표와 족보 낱말을 세어 본 값일 뿐이다. "
                     "`260813_03`에서는 이 방식이 통째로 틀렸다 — 표지 문구가 "
                     "'정답'이라 못 잡았고, 문항 본문이 이미지라 빈 페이지 폴백도 "
                     "안 걸렸다. **네 판정이 주인이다.**")
        lines.append("")
        lines.append(f"다만 검증기가 둘의 차이를 잰다. **{scanned}과 3장 넘게 "
                     "차이나면 검증이 멈춘다** — 그때는 원본을 보고 어느 쪽이 맞는지 "
                     "가려서 `jokbo_evidence`에 적어라.")

    external = prep.get("external_jokbo_range")
    if external:
        lo, hi = int(external[0]), int(external[1])
        lines += [
            "",
            f"### 외부 족보가 붙어 있다 — 슬라이드 {lo}~{hi}",
            "",
            f"필기는 {total}쪽이고 거기에 별도 족보 PDF {hi - lo + 1}장을 이어 붙여 "
            f"자료 전체가 {prep.get('total_slides')}장이 됐다.",
            "",
            f"**`jokbo_range`는 한 구간으로 적는다** — 필기 꼬리의 족보가 시작하는 "
            f"쪽부터 {hi}까지다. 필기에 꼬리가 없으면 {lo}부터다. 검증기는 필기 "
            f"안쪽({total}쪽까지)만 수치로 따지고 바깥쪽은 별도 파일이라 안 따진다.",
        ]
    return "\n".join(lines)


def read_plan(prep: dict, features: list[PageFeature]) -> str:
    """남는 읽기 하나. 필기 꼬리 족보는 캡처 이미지라 글자가 안 잡힌다."""
    scanned = scan_jokbo_start(features)
    annotated = prep.get("annotated_pdf")
    if not annotated:
        return ""
    total = len(features)
    lo = max(1, (scanned or total) - 3)
    return (
        "## 눈으로 볼 곳 하나\n\n"
        f"필기 꼬리에 붙은 족보는 **캡처 이미지**라 글자가 거의 안 잡힌다 — 위 표에서 "
        f"그 구간의 글자수가 수십 자로 떨어지는 것이 그 때문이다. 그래서 여기만 "
        f"직접 본다.\n\n"
        f"    Read(\"{Path(annotated).as_posix()}\", pages=\"{lo}-{total}\")\n\n"
        "경계가 정말 거기인지 확인하고, 그 김에 **문항을 읽어 `exam_focus`를 쓴다.** "
        "이 읽기를 여기서 한 번 하는 것이 1단계 조각들이 각자 다시 읽는 것보다 싸다."
    )


def rules_section(features: list[PageFeature]) -> str:
    """검증기가 실제로 따지는 것. `quiz/structure.py`의 `verify`를 옮겼다.

    **여기 적힌 것과 코드가 어긋나면 코드가 주인이다.** 검증이 멈추면 이 절을
    먼저 의심하라 — 규칙이 바뀌었는데 이 문구가 안 따라온 것일 수 있다.
    """
    total = len(features)
    return f"""\
## 검증기가 따지는 것

네가 쓰면 `quiz/structure.py`가 수치로 따진다. 하나라도 걸리면 멈추고 다시 시킨다.
**미리 맞춰서 써라.**

### 경계

- `lecture_range`는 1~{total} 안에 있어야 한다
- 강의록과 족보가 **겹치면 안 되고, 사이가 비어도 안 된다.**
  `lecture_range`의 끝 + 1 = `jokbo_range`의 시작
- 족보 구간은 **2장 이상**이어야 한다. 한 장짜리는 강의록 마무리 슬라이드일 때가 많다
- 족보 시작은 문서 **뒤쪽 절반**({total // 2}쪽 이후)이어야 한다
- 족보 구간에 **답안 나열이나 족보 낱말이 최소 한 번**은 나와야 한다
- 족보 구간의 글자수 중앙값이 강의록 중앙값의 **절반을 넘으면** 안 된다.
  구간 안에 강의록 수준 본문이 **한 장이라도** 섞여 있어도 걸린다
- 강의록 구간에 **답안 나열이 2줄 이상인 페이지**가 있으면 걸린다.
  답안표는 강의록에 없다 — 있으면 그 페이지는 족보다
- 족보가 없다고 적었는데 뒤쪽 40%에 답안 나열이 3번 이상 나오면 걸린다

### 주제 덩어리

- `chunks`가 `lecture_range`를 **빠짐없이·겹침없이** 덮어야 한다.
  첫 조각은 `lecture_range`의 시작에서, 마지막 조각은 그 끝에서 맺는다
- 조각 하나는 **{CHUNK_SLIDES_MAX}장을 넘기지 마라.** 1단계가 조각 PDF를 통째로
  읽어야 텍스트 레이어가 따라오는데, {CHUNK_SLIDES_MAX}쪽을 넘으면 그 읽기가
  거부되어 그림만 보게 된다
- 실측에서는 조각당 {CHUNK_SLIDES_TYPICAL}장이었다. 한도가 아니라 관찰이다 —
  **주제가 가르는 대로 갈라라.** 장수를 맞추려고 주제를 쪼개지 마라
- 표지·학습목표·참고자료도 어느 조각엔가 들어가야 한다. 덮지 않으면 검증이 멈춘다.
  1단계가 거기서 카드를 안 내는 것은 그쪽에서 판단한다"""


def output_section(run_dir: Path) -> str:
    out = run_dir / "structure.json"
    return f"""\
## 출력

`{out}`에 JSON 하나로 쓴다. 그것 말고는 아무 파일도 만들거나 고치지 않는다.

```json
{{
  "lecture_id": "{run_dir.name}",
  "lecture_range": [1, 67],
  "jokbo_range": [68, 89],
  "jokbo_evidence": "왜 거기가 경계인지. 슬라이드 번호를 대고 무엇이 보였는지 적는다.",
  "chunks": [
    {{"id": "c01", "title": "표지와 강의 개요", "slides": [1, 5],
     "summary": "이 덩어리가 무엇을 다루는지 한 줄"}}
  ],
  "exam_focus": {{"...": "모양은 자유다"}}
}}
```

- `id`는 `c01`부터 이어 붙인다. 1단계가 이 이름으로 조각 PDF와 결과 파일을 만든다
- **`jokbo_evidence`는 짧게 쓰지 마라.** 다음에 이 편을 다시 볼 사람이
  경계를 의심할 때 읽는 유일한 글이다. 무엇이 어느 쪽에서 보였는지 대라
- `jokbo_range`는 족보가 없으면 `null`로 둔다
- `exam_focus`는 **1단계 조각 전부가 읽는다.** 어느 해에 어느 교수가 무엇을
  물었는지, 어느 선지가 어떻게 뒤집혔는지가 여기 있으면 조각이 족보를 다시
  읽지 않는다. 모양은 정해두지 않았다 — 세지 않고 그대로 넘긴다"""


def spawn_prompt(run_dir: str | Path, *, with_jokbo_text: bool = True) -> str:
    run_dir = Path(run_dir)
    prep = json.loads((run_dir / "prep.json").read_text(encoding="utf-8"))
    features = load_features(run_dir, prep)
    total = len(features)

    parts = [
        f"# 0.5단계 — `{prep.get('lecture_id')}` 「{prep.get('lecture_title')}」의 구조를 정한다",
        (f"필기 {total}쪽짜리 강의록이다. 어디까지가 강의록이고 어디부터가 족보인지, "
         f"그리고 강의록을 어떤 주제 덩어리로 가를지를 정한다.\n\n"
         f"**이 판정 하나에 뒤가 전부 걸린다.** 강의록을 족보로 오인하면 clean 채널을 "
         f"잃고, 족보를 강의록으로 오인하면 기출이 통째로 사라진다."),
        outline_table(run_dir, prep),
        feature_table(features),
        machine_hint(features, prep),
        read_plan(prep, features),
        rules_section(features),
    ]

    jokbo_file = run_dir / "jokbo_text.md"
    if with_jokbo_text and jokbo_file.exists():
        parts.append(
            "## 외부 족보 원문\n\n"
            "`exam_focus`를 쓰는 데 쓴다. 필기 꼬리의 족보는 위 「눈으로 볼 곳」에서 "
            "따로 본다 — 둘은 서로를 대체하지 않는다.\n\n"
            f"```\n{jokbo_file.read_text(encoding='utf-8').strip()}\n```"
        )

    parts.append(DO_NOT)
    parts.append(output_section(run_dir))
    return "\n\n".join(p.strip() for p in parts if p and p.strip())


def build(run_dir: str | Path, *, with_jokbo_text: bool = True) -> dict:
    run_dir = Path(run_dir)
    text = spawn_prompt(run_dir, with_jokbo_text=with_jokbo_text)
    out_dir = run_dir / "spawn"
    out_dir.mkdir(parents=True, exist_ok=True)
    spawn_file = out_dir / "structure.md"
    spawn_file.write_text(text, encoding="utf-8")
    return {
        "spawn_prompt": str(spawn_file),
        "result": str(run_dir / "structure.json"),
        "chars": len(text),
        "approx_tokens": len(text) // 2,
        "jokbo_text_attached": with_jokbo_text and (run_dir / "jokbo_text.md").exists(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="0.5단계: structure.json을 쓸 스폰 문구를 만든다")
    parser.add_argument("run_dir", help="runs/<lecture_id>")
    parser.add_argument("--no-jokbo-text", action="store_true",
                        help="외부 족보 원문을 안 붙인다 (exam_focus가 얕아진다)")
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    with timings.stage(run_dir, "0.5-plan"):
        row = build(run_dir, with_jokbo_text=not args.no_jokbo_text)
    print(f"[structure] {row['spawn_prompt']}")
    print(f"  {row['chars']:,}자 (대략 {row['approx_tokens']:,}토큰)"
          + ("  · 족보 원문 붙임" if row["jokbo_text_attached"] else ""))
    print(f"\n  서브에이전트 하나에게 그 파일을 읽고 그대로 따르라고만 시킨다.")
    print(f"  → {row['result']}")
    print(f"\n  띄우기 직전·받은 직후에 찍어라 — 안 찍으면 그 시간이 사라진다:")
    print(f"      python -m quiz2.timings {run_dir} start 0.5-write")
    print(f"      python -m quiz2.timings {run_dir} end   0.5-write")
    print(f"\n  쓴 뒤 검증:  python quiz/structure.py {run_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
