"""예습 프롬프트를 완제품으로 조립한다.

복습 쪽(`pdf2anki.assemble`)과 기계는 같고 **철학만 다르다.**
토큰 예산·파트 나누기·PDF 읽히는 지시는 `pdf2anki.pack` 이 공유하고,
여기 있는 것은 '무엇을 왜 강조하는가' 뿐이다.

가장 크게 갈리는 자리는 **족보의 용법**이다.
복습은 기출을 *예측*으로 쓴다 — 이게 올해 나올 것 같다.
예습은 기출을 *중심성의 증거*로만 쓴다 — 여러 해 물었다면 이 단원의 중심이다.

사용:
    python -m pdf2anki.prequiz.assemble out/pre_xxx --jokbo-dir out/jokbo
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ..assemble import NO_JOKBO_DIR, NO_JOKBO_MATCH
from ..pack import (
    READ_TOKEN_CAP,
    estimate_pdf_tokens,
    find_jokbo,
    needs_clean,
    read_instructions,
    write_parts,
)
from ..prompting import DEFAULT_DOMAIN, DOMAINS, lecture_adapters, read_modules

PROMPTS = Path(__file__).parent / "prompts"

# ② 는 ① 세션을 이어받으므로 자료·철학·계약을 다시 싣지 않는다.
# 무엇이 이미 있는지만 짚어 준다.
CARRY_OVER = """# ② 카드

앞 단계에서 읽은 것이 전부 그대로 있다 — 강의 PDF, 사이드카, 기출 조각,
예습 설명본, 출제 철학, 출력 계약, 그리고 네가 세운 `must_know`.
**다시 읽지 마라.** 아래 할 일만 하면 된다.
"""


def professor_line(stats: dict) -> tuple[bool, str]:
    """(교수가 유임인가, 사람이 읽을 한 줄).

    `reason=repeated` 를 쓸 수 있는지가 여기서 갈린다. 교수가 바뀌었으면 과거의 반복은
    이전 교수의 습관이지 이 단원의 중심이 아니다.
    """
    yr = stats.get("professors_by_year") or {}
    line = " · ".join(f"20{y} {'/'.join(v)}" for y, v in sorted(yr.items(), reverse=True))
    stayed = not stats.get("professor_changed_2026", False) and bool(stats.get("professor_2026"))
    return stayed, line or "미상"


def jokbo_guidance(stats: dict, title: str, mixed: list | None = None,
                   shared_bank: bool = False) -> str:
    """예습용 족보 지침. 기출을 **예측이 아니라 중심성의 증거로** 쓰게 한다."""
    stayed, prof = professor_line(stats)
    rate = stats.get("repeat_rate", 0.0)
    pairs = stats.get("repeat_pairs") or []

    head = (f"## 이 강의의 기출 사정\n\n"
            f"- 조각의 주 섹션: {title}\n"
            f"- 담당 교수: {prof}\n"
            f"- 연도간 문항 반복률: {rate:.0%} (문항 {stats.get('n_questions', 0)}개)\n")

    if stayed:
        body = ("**담당 교수가 유임이다.** 과거에 여러 해 반복해서 물은 주제는 "
                "이 교수가 이 단원의 중심이라고 보는 것이므로, `reason=repeated` 를 쓸 수 있다.\n\n"
                "**다만 기출을 예측으로 쓰지 마라.** '올해 나올 것 같다'는 복습 덱의 판단이고 "
                "이 덱의 것이 아니다. 여기서 기출이 말해 주는 것은 하나뿐이다 — "
                "*이 단원에서 무엇이 중심 개념인가.*\n\n"
                "그리고 기출은 **다섯 번째 근거**다. 강의록의 구조, 처음 등장하는 용어·약어, "
                "작년 필기가 몰린 곳, 예습 설명본을 먼저 본 뒤에 기출을 얹어라. "
                "기출이 물었다는 이유만으로 카드를 만들지 마라 — "
                "그 문항이 요구한 지식이 *수업을 따라가는 데 필요한가* 를 따로 물어야 한다.")
        if rate < 0.25:
            body += (f"\n\n> 반복률이 {rate:.0%}로 낮다. 이 교수는 기출을 그대로 재활용하지 않는다. "
                     f"`reason=repeated` 는 아래 실제 반복 쌍에 한해서만 쓰고, "
                     f"나머지는 강의록과 필기에서 중심을 찾아라.")
    else:
        body = ("**올해 담당 교수가 바뀌었다.** 과거 기출은 이전 교수의 출제이므로 "
                "그 반복이 이 단원의 중심을 뜻하지 않는다.\n\n"
                "**`reason=repeated` 를 쓰지 마라.** 기출은 '이 단원에서 무엇이 시험 가능한 "
                "지식이었나' 정도의 배경으로만 읽고, 중심은 강의록의 구조와 작년 필기가 "
                "몰린 곳에서 찾아라.\n\n"
                "예습이 겨냥하는 것은 '꼭 반드시 알아야 할 의학 지식'이고, 그것은 강의자가 "
                "바뀌어도 대체로 그대로다. 교수 교체는 이 덱에서 기출의 무게를 낮출 뿐 "
                "덱의 축을 바꾸지 않는다.")

    if pairs and stayed:
        rows = "\n".join(f"- {p['a']} ↔ {p['b']}  (유사도 {p['jaccard']:.2f})" for p in pairs[:8])
        body += ("\n\n### 실제로 여러 해 반복된 문항\n\n"
                 "이 쌍들이 가리키는 **개념**이 중심성의 직접 증거다. 문항의 형태가 아니라 "
                 "그것이 요구한 지식을 보아라.\n\n" + rows)

    mix = ""
    if shared_bank:
        mix += ("\n> ⚠ **이 조각은 실습 전 회차의 문항을 한데 모은 것이다.** "
                "이번 강의 소관 문항만 골라 써라.\n")
    if mixed:
        mix += ("\n> ⚠ **이 조각의 주인은 다른 강의다.** 아래 강의가 이 섹션으로 흘러들어와 있다.\n"
                + "".join(f"> - {m['lecture_key']} {m['title']}\n" for m in mixed))
    return head + mix + "\n" + body + "\n"


def assemble(prep_dir: Path, jokbo_file: Path | None, schema_dir: Path,
             note_file: Path | None = None, domain: str = DEFAULT_DOMAIN) -> dict:
    prep = json.loads((prep_dir / "prep.json").read_text(encoding="utf-8"))
    prep_md = (prep_dir / "prep.md").read_text(encoding="utf-8")
    contract = (schema_dir / "contract.md").read_text(encoding="utf-8")
    pdf = (prep_dir / prep["annotated_pdf"]).resolve()

    if jokbo_file:
        jk = json.loads(jokbo_file.read_text(encoding="utf-8"))
        jokbo_md = jokbo_file.with_suffix(".md").read_text(encoding="utf-8")
        guidance = jokbo_guidance(jk["stats"], f"{jk['lecture_key']} {jk['title']}",
                                  jk.get("may_contain"),
                                  shared_bank=jk["lecture_key"] == "PRAC")
        jokbo_block = (f"# 기출 조각 — {jk['lecture_key']} {jk['title']}\n\n"
                       "이 단원의 과거 기출 전량이다. **예습에서는 중심성의 증거로만 읽는다** — "
                       "무엇이 이 단원의 중심 개념인지를 알려줄 뿐, 무엇이 올해 나올지를 "
                       "말해 주지 않는다.\n\n" + jokbo_md.split("\n", 1)[1].lstrip())
    else:
        jk = None
        guidance = ("## 이 강의의 기출 사정\n\n기출 조각이 없다. "
                    "강의록의 구조와 작년 필기만으로 중심을 찾아라.\n")
        jokbo_block = ""

    sidecar = "# 슬라이드 사이드카 (작년 필기본)\n\n" + prep_md.split("\n", 1)[1]
    adapters = lecture_adapters(has_past_exam=bool(jokbo_file), domain=domain)
    shared_prompt = read_modules(profile="prelecture", adapters=adapters,
                                 domain=domain)

    note_block = ""
    if note_file and note_file.exists():
        note_block = ("# 예습 설명본\n\n"
                      "작년 필기를 예습용으로 풀어 쓴 글이다. **이미 예습의 관점으로 고른 것**이라 "
                      "무엇이 중심인지의 강한 신호다. 근거로 쓰되 그대로 베끼지 마라 — "
                      "이 글이 다루지 않은 용어·약어가 강의록에 있으면 그것도 카드다.\n\n"
                      + note_file.read_text(encoding="utf-8").strip())

    ctx_sections = [sidecar] + ([note_block] if note_block else []) \
        + ([jokbo_block] if jokbo_block else [])
    ctx_files = write_parts(prep_dir, "context", ctx_sections, label="자료 파트")
    ctx_names = [f["name"] for f in ctx_files]

    head = (f"# 강의 → 예습 덱 : {prep['source']}\n\n"
            "너는 **내일 이 강의를 처음 듣는 사람**을 위한 예습 덱을 만든다.\n"
            "이 PDF 는 **작년** 필기본이다 — 올해 필기는 아직 존재하지 않는다.\n"
            "자료는 여기와 아래 지정한 파일에 전부 있다. 그 밖의 파일을 찾아다니지 마라.\n\n"
            + read_instructions(pdf, prep["slides"], [prep_dir / n for n in ctx_names],
                                (prep_dir / prep["clean_pdf"]).resolve(),
                                needs_clean(prep))
            + "\n" + guidance)

    out = {"context": ctx_files}
    for stage, task_file, subs in (
        ("must", "must.md", {"must_out": (prep_dir / "must_know.json").as_posix()}),
        ("cards", "cards.md", {"must_in": (prep_dir / "must_know.approved.json").as_posix(),
                               "cards_out": (prep_dir / "items.raw.json").as_posix()}),
    ):
        task = (PROMPTS / task_file).read_text(encoding="utf-8")
        for k, v in subs.items():
            task = task.replace("{" + k + "}", v)
        # **②는 ①의 세션을 이어받는다.** 머리말·철학·계약은 이미 컨텍스트에 있으므로
        # 다시 실으면 그 15k 가 남은 턴마다 따라다닌다. ②에는 할 일만 준다.
        sections = ([head, *shared_prompt, task, contract] if stage == "must"
                    else [CARRY_OVER, task])
        out[stage] = write_parts(prep_dir, f"prompt.{stage}", sections, manifest=True)

    out["_pdf_tokens"] = estimate_pdf_tokens(prep)
    out["_jokbo"] = jk
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="예습 프롬프트를 조립한다")
    ap.add_argument("prep_dir")
    ap.add_argument("--jokbo", help="족보 조각 json. 생략하면 목차 제목으로 자동 대조한다")
    ap.add_argument("--jokbo-dir", default="out/jokbo")
    ap.add_argument("--schema-dir", default="out/prequiz_schema")
    ap.add_argument("--note", help="예습 설명본 (굳혀 둔 note.md). 기본은 폴더 안의 note.md")
    ap.add_argument("--domain", default=DEFAULT_DOMAIN, choices=sorted(DOMAINS),
                    help=f"퀴즈 도메인 정책 (기본 {DEFAULT_DOMAIN})")
    args = ap.parse_args(argv)

    prep_dir = Path(args.prep_dir)
    prep = json.loads((prep_dir / "prep.json").read_text(encoding="utf-8"))

    jokbo_file = Path(args.jokbo) if args.jokbo else None
    # **폴더가 없을 때 아무 말도 안 하던 자리다.** 복습 쪽이 그 침묵으로 7편을 기출
    # 0장으로 내보냈고(`assemble.slice_for`), 여기도 같은 모양이었다. 예습에서 잃는
    # 것은 기출 카드가 아니라 **중심성의 증거**다 — `reason=repeated` 를 쓸 근거가
    # 통째로 없어지는데 화면에는 한 줄도 안 떴다.
    if jokbo_file is None and not (Path(args.jokbo_dir) / "index.json").exists():
        print(NO_JOKBO_DIR.format(index=Path(args.jokbo_dir) / "index.json"), flush=True)
    elif jokbo_file is None:
        jokbo_file, score, top = find_jokbo(prep, Path(args.jokbo_dir))
        print("족보 조각 자동 대조:")
        for sc, e, via in top:
            mark = " ←선택" if jokbo_file and e["file"] in jokbo_file.name else ""
            label = (f"{e['lecture_key']} {e['title']}" if not via
                     else f"{via['lecture_key']} {via['title']}  "
                          f"(조각은 {e['lecture_key']} 안에 섞여 있음)")
            print(f"   {sc:.2f}  {label}{mark}")
        if not jokbo_file or score < 0.25:
            print(NO_JOKBO_MATCH.format(score=score), flush=True)
            jokbo_file = None

    note = Path(args.note) if args.note else (prep_dir / "note.md")
    if note.exists():
        print(f"예습 설명본: {note.name}")
    else:
        print("예습 설명본 없음 — 강의록·필기·기출만으로 간다")
        note = None

    if jokbo_file:
        stats = json.loads(jokbo_file.read_text(encoding="utf-8")).get("stats", {})
        stayed, prof = professor_line(stats)
        print(f"교수 {'유임' if stayed else '교체'} ({prof}) · "
              f"반복률 {stats.get('repeat_rate', 0):.0%} → "
              f"reason=repeated {'사용 가능' if stayed else '금지'}")

    res = assemble(prep_dir, jokbo_file, Path(args.schema_dir), note, args.domain)

    print()
    for stage in ("context", "must", "cards"):
        for f in res[stage]:
            warn = "  ⚠ Read 상한 초과" if f["tokens"] > READ_TOKEN_CAP else ""
            print(f"[{stage:7}] {f['name']:26} {f['chars']:>7,}자  {f['tokens']:>7,}토큰{warn}")
    ctx = sum(f["tokens"] for f in res["context"])
    must = sum(f["tokens"] for f in res["must"])
    cards = sum(f["tokens"] for f in res["cards"])
    print("\n한 세션에서 ①②를 이어 하면 PDF와 자료는 한 번만 읽는다:")
    print(f"   PDF {res['_pdf_tokens']:,} + 자료 {ctx:,} + ① {must:,} + ② {cards:,} "
          f"= 약 {res['_pdf_tokens'] + ctx + must + cards:,}토큰")
    return 0


if __name__ == "__main__":
    sys.exit(main())
