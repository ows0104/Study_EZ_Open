"""조각 하나에 줄 스폰 프롬프트를 조립한다.

## 이 모듈이 없애려는 것

v1 조각 하나를 뜯어보니 도구 호출 47회 중 **26회가 입력을 스스로 찾는 데** 쓰였다.

    규칙·스키마·validate.py 소스 읽기                    5회
    blueprint·structure·annotations·labels 뒤지기      13회
    PDF·PNG 읽기                                        8회
    ─────────────────────────────────────────────────
                                                       26회

그리고 매 호출이 문맥 12만 토큰을 다시 읽었다. **찾을 것을 안 남기면 26회가 0이
된다.** 규칙은 문자열로 박아 넣고, 자료는 조각별로 잘라 두고, 읽을 파일을 이름으로
찍어 준다.

## 그래서 프롬프트에 "하지 마라"가 들어간다

허용이 기본이라는 원칙(CLAUDE.md ②)의 예외다. 근거가 실측이라 남긴다 — 안 적으면
에이전트가 규칙 문서를 찾아 읽고, `validate.py`를 돌리고, `Edit`을 일곱 번 건다.
그게 v1에서 실제로 일어난 일이다.

## 남는 것

    텍스트 조각   Read 1~2회(잘라 둔 PDF) + Write 1회
    오클루전 조각  거기에 렌더·확인 반복이 붙는다 (단발로 안 되는 유일한 작업)
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

from quiz import timings  # noqa: E402

from . import chunks as chunks_mod
from . import prompt as prompt_mod


# 실측 근거가 있는 금지만 적는다. 각 줄이 v1에서 실제로 일어난 낭비다.
DO_NOT = """\
## 하지 말 것 (이게 이 방식의 핵심이다)

필요한 것은 **전부 위에 있거나 아래 파일 목록에 있다.** 찾으러 가지 마라.

- **규칙 문서를 찾아 읽지 마라.** 출제 규칙은 이 프롬프트에 전문이 들어 있다
- **`blueprint.json`·`structure.json`·`labels.json`·`outline.json`을 열지 마라.**
  네가 쓸 것은 아래 목록의 파일뿐이다
- **`validate.py`를 돌리지 마라.** 스키마·범위·중복·길이는 코드가 사후에 센다
- **쓴 뒤에 고쳐 쓰지 마라.** 한 번에 완성해서 한 번만 써라.
  v1은 여기서 `Edit`을 일곱 번 걸었고 그때마다 문맥 12만 토큰을 다시 읽었다
- **다른 조각의 슬라이드를 보지 마라.** 네 구간만 맡는다
"""


def jokbo_scope(prep: dict) -> str:
    """족보 구간이 이 편 말고 다른 강의도 담고 있으면 그렇다고 알려 준다.

    과목 족보는 **단원**으로 갈려 있고 단원이 강의와 1:1이 아니다. `L13-15
    유전질환 (1)~(3)`은 강의 13·14·15를 한 덩어리로 담고, 같은 파일이 세 편에
    똑같이 붙는다.

    1회차에서 이것 때문에 족보 카드 44장 중 절반 넘게가 남의 강의 몫이었다 —
    Turner·Klinefelter·Down·Robertsonian translocation이 '단일유전자질환' 덱에
    들어갔다. 그대로 두면 세 편이 같은 카드를 세 번 만든다.

    **분할기로는 못 가른다.** 원본 안에 강의 경계 표시가 없고 연도로만 묶여 있어,
    문항 하나씩 주제를 보고 판단해야 한다. 그건 모델의 몫이라 여기서 말로 넘긴다.
    """
    jokbo_pdf = prep.get("jokbo_pdf")
    title = (prep.get("lecture_title") or "").strip()
    if not jokbo_pdf or not title:
        return ""
    index_file = Path(jokbo_pdf).parent / "index.json"
    if not index_file.exists():
        return ""
    try:
        sections = json.loads(index_file.read_text(encoding="utf-8"))["sections"]
    except (KeyError, ValueError):
        return ""
    mine = next((s for s in sections
                 if Path(s.get("pdf", "")).name == Path(jokbo_pdf).name), None)
    if not mine or len(mine.get("lectures") or []) <= 1:
        return ""

    numbers = ", ".join(str(n) for n in mine["lectures"])
    return (
        f"## 이 족보는 강의 여러 편을 함께 담고 있다\n\n"
        f"붙어 있는 족보 구간은 **`{mine['title']}`**이고 강의 {numbers}번을 한 덩어리로\n"
        f"묶은 것이다. 연도별로만 정렬돼 있고 강의별 경계는 없다.\n\n"
        f"**이 편은 그중 「{title}」 하나다.**\n\n"
        f"다른 강의 주제의 문항은 **카드로 만들지 마라.** 대신 `rejected_candidates`에\n"
        f"`redundant`로 남겨라 — 그 문항은 그 강의를 맡은 편이 가져간다.\n"
        f"판단이 애매하면 이 강의 본문에서 다루는 개념인지로 가른다."
    )


def _file_list(chunk: chunks_mod.ChunkPdf, *, include_annot: bool) -> str:
    """읽을 파일을 이름으로 찍는다. 여기 없는 것은 열 이유가 없다."""
    lines = [f"1. **`{chunk.path}`** — clean 채널. **사실 근거는 여기서만 나온다.**",
             f"   `pages` 없이 통째로 읽어라 ({chunk.pages}쪽이라 상한에 안 걸리고,"
             f" 그래야 텍스트 레이어까지 온다)"]
    n = 2
    if include_annot and chunk.annot_path:
        lines.append(f"{n}. **`{chunk.annot_path}`** — 필기본. 같은 슬라이드에 "
                     f"필기가 얹힌 것. 표시 {chunk.mark_count}개, 필기자의 말 "
                     f"{chunk.note_count}개")
        n += 1
    if chunk.notes_path:
        lines.append(f"{n}. **`{chunk.notes_path}`** — 필기자의 말과 "
                     f"표시가 덮은 낱말(`covers`)")
    return "\n".join(lines)


def spawn_prompt(
    chunk: chunks_mod.ChunkPdf,
    *,
    out_path: str | Path,
    exam_focus: str = "",
    jokbo_text: str = "",
    scope_note: str = "",
    give_card_types: bool = True,
) -> str:
    """이 조각을 맡을 서브에이전트에게 통째로 건넬 문구.

    `exam_focus`는 족보에서 읽어낸 출제 성향 요약이고, `jokbo_text`는 족보 원문
    전문이다. **둘 중 하나를 고르는 것이 아직 안 정해졌다** — 요약은 싸지만
    "어느 선지가 어떻게 뒤집혔는지"가 뭉개지고, 원문은 조각당 4천 토큰쯤 든다.
    v1에서 요약만 준 탓에 조각 셋이 맞는 인용 20건을 지운 사고가 있었다.
    지금은 둘 다 받고, 주는 쪽이 정한다.

    필기가 없는 조각(`mark_count == 0`)에는 필기본을 안 붙인다 — 볼 게 없는
    쪽 이미지를 배로 보내는 값이 아깝다.
    """
    is_jokbo = chunk.chunk_id == "jokbo"
    include_annot = bool(chunk.annot_path) and chunk.mark_count > 0

    parts = [
        f"# 조각 `{chunk.chunk_id}` — 슬라이드 {chunk.slides[0]}~{chunk.slides[1]}",
        "이 구간의 Anki 카드를 만든다. 아래 규칙이 전부이고, 읽을 파일도 아래가 전부다.",
        "## 읽을 파일\n\n" + _file_list(chunk, include_annot=include_annot),
    ]

    if include_annot:
        parts.append(chunks_mod.HIERARCHY)
    elif not is_jokbo:
        parts.append("## 필기\n\n이 구간에는 필기 표시가 없다. clean 채널만 보면 된다.")

    parts.append(prompt_mod.make_prompt(
        slide_start=chunk.slides[0], slide_end=chunk.slides[1],
        source_type="jokbo" if is_jokbo else "lecture",
        exam_focus=exam_focus, give_card_types=give_card_types,
    ))

    if is_jokbo and scope_note.strip():
        parts.append(scope_note.strip())

    if jokbo_text.strip() and not is_jokbo:
        parts.append(
            "## 족보 원문\n\n이 강의 단원의 기출이다. 어느 지점이 실제로 출제됐는지"
            " 보고 `exam_hit`을 정하는 데 쓴다. 요약이 아니라 원문이므로 선지까지"
            f" 그대로 있다.\n\n```\n{jokbo_text.strip()}\n```"
        )

    if not chunk.has_text_layer:
        parts.append(
            f"## 이 조각은 그림 위주다\n\n{chunk.pages}쪽 중 {chunk.blank_pages}쪽에"
            " 텍스트 레이어가 거의 없다. 원문 표기를 텍스트로 대조할 수 없으니"
            " **그림에서 읽은 철자를 그대로 옮겨 적을 때 특히 조심하라.**"
        )

    parts.append(DO_NOT)
    parts.append(
        f"## 출력\n\n`{out_path}`에 JSON 하나로 쓴다. 그것 말고는 아무 파일도"
        " 만들거나 고치지 않는다.\n\n"
        "```json\n"
        '{\n'
        '  "learning_plan": [\n'
        '    {"objective": "...", "retrieval_targets": ["..."],\n'
        '     "rejected_candidates": [{"candidate": "...", "reason": "decorative"}]}\n'
        '  ],\n'
        '  "cards": [\n'
        '    {"q": "...", "a": "...", "explanation": "...", "slide_no": 0,\n'
        '     "card_type": "fact", "card_format": "basic",\n'
        '     "importance": "core", "exam_hit": false,\n'
        '     "evidence_type": "lecture_text", "source_type": "lecture",\n'
        '     "review_note": null}\n'
        '  ]\n'
        '}\n'
        "```"
    )
    return "\n\n".join(p.strip() for p in parts)


def build_all(run_dir: str | Path, *, give_card_types: bool = True,
              with_jokbo_text: bool = True) -> list[dict]:
    """편 하나의 조각 전부에 대해 스폰 문구를 만들어 파일로 남긴다.

    오케스트레이터는 이 목록을 받아 조각마다 서브에이전트를 하나씩 띄우면 된다.
    """
    run_dir = Path(run_dir)
    made = chunks_mod.write_chunk_pdfs(run_dir)
    structure = json.loads((run_dir / "structure.json").read_text(encoding="utf-8"))
    prep = json.loads((run_dir / "prep.json").read_text(encoding="utf-8"))
    scope_note = jokbo_scope(prep)
    exam_focus = structure.get("exam_focus") or ""
    if not isinstance(exam_focus, str):
        exam_focus = json.dumps(exam_focus, ensure_ascii=False, indent=1)

    jokbo_text = ""
    jokbo_file = run_dir / "jokbo_text.md"
    if with_jokbo_text and jokbo_file.exists():
        jokbo_text = jokbo_file.read_text(encoding="utf-8")

    out_dir = run_dir / "spawn"
    out_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict] = []
    for chunk in made:
        result_path = run_dir / f"items.raw.{chunk.chunk_id}.json"
        text = spawn_prompt(chunk, out_path=result_path, exam_focus=exam_focus,
                            jokbo_text=jokbo_text, scope_note=scope_note,
                            give_card_types=give_card_types)
        spawn_file = out_dir / f"{chunk.chunk_id}.md"
        spawn_file.write_text(text, encoding="utf-8")
        rows.append({
            "chunk_id": chunk.chunk_id,
            "slides": list(chunk.slides),
            "spawn_prompt": str(spawn_file),
            "result": str(result_path),
            "chars": len(text),
            "approx_tokens": len(text) // 2,
            "annot_attached": bool(chunk.annot_path) and chunk.mark_count > 0,
            "scoped": bool(scope_note) and chunk.chunk_id == "jokbo",
        })
    (out_dir / "index.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    return rows


def main() -> int:
    """`python -c "from quiz2 import assemble; ..."`를 대신한다.

    명령이 되어야 스스로 계측을 찍는다 — 코드 단계는 자기가 찍는다는 규칙
    (`quiz2/timings.py`의 `STAGES`)을 이 단계만 못 지키고 있었다.
    """
    parser = argparse.ArgumentParser(description="1단계: 조각 PDF와 스폰 문구")
    parser.add_argument("run_dir")
    parser.add_argument("--no-card-types", action="store_true",
                        help="⑨′ A/B 스위치. card_type 목록을 안 준다")
    parser.add_argument("--no-jokbo-text", action="store_true",
                        help="족보 원문을 조각에 안 붙인다 (요약만 간다)")
    args = parser.parse_args()
    run_dir = Path(args.run_dir)

    with timings.stage(run_dir, "1-assemble"):
        rows = build_all(run_dir, give_card_types=not args.no_card_types,
                         with_jokbo_text=not args.no_jokbo_text)

    print(f"[assemble] 조각 {len(rows)}개 → {run_dir / 'spawn'}")
    for row in rows:
        print(f"  {row['chunk_id']:<6} 슬라이드 {row['slides'][0]:>3}-{row['slides'][1]:<3}"
              f"  {row['approx_tokens']:>6,}토큰"
              + ("  필기본 붙임" if row["annot_attached"] else "")
              + ("  범위 제한" if row.get("scoped") else ""))
    print("\n조각마다 서브에이전트를 하나씩, 동시에 돌린다.")
    print("띄우기 직전·받은 직후에 찍어라 — 편 시간의 대부분이 여기다:")
    print(f"    python -m quiz2.timings {run_dir} start 2-write --label c01")
    print(f"    python -m quiz2.timings {run_dir} end   2-write --label c01")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
