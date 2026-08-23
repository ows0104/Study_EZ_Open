"""모델이 읽을 프롬프트를 완제품으로 조립한다.

모델에게 규칙·스키마·자료를 찾아다니게 하지 않는다. 코드가 한 파일로 묶어 준다.
텍스트는 전부 인라인하고, 파일로 남기는 것은 PDF 뿐이다(Read 로 읽어야 하므로).

두 개를 만든다.
  prompt.plan.md    ① 학습 목표만 세운다. 사람이 승인한다.
  prompt.cards.md   ② 승인된 목표를 카드로 만든다.

사용:
    python -m pdf2anki.assemble out/lec03 --jokbo-dir out/jokbo
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .pack import (READ_TOKEN_CAP, estimate_pdf_tokens, find_jokbo,
                   needs_clean, read_instructions, write_parts)

PROMPTS = Path(__file__).parent / "prompts"
# ── 전략 ──────────────────────────────────────────────────────────
# 세 갈래뿐이다. 축은 하나 — **이번 시험의 출제자가 누구의 강조점을 물을 것인가.**
#   annotation(필기 중심)  교수가 바뀌었다. 강의록은 작년 것이고 기출은 이전 교수의 출제다.
#                          올해 필기만이 지금 교수가 실제로 말한 기록이다.
#   jokbo(족보 중심)       교수가 유임이고 기출을 재활용한다. 기출이 물은 것을 먼저 덮는다.
#   base(기본)             교수는 유임이나 반복률이 낮다. 강의록을 훑고 기출은 신호로만 쓴다.
STRATEGIES = {"annotation": "필기 중심", "jokbo": "족보 중심", "base": "기본"}
STRATEGY_ALIAS = {"필기": "annotation", "족보": "jokbo", "기본": "base",
                  "annotation": "annotation", "jokbo": "jokbo", "base": "base",
                  "auto": "auto"}


def decide_strategy(stats: dict | None, mixed_owner: bool = False) -> tuple[str, str]:
    """(전략, 고른 이유 한 줄). 교수 교체를 반복률보다 먼저 본다.

    교수가 바뀌면 반복률이 아무리 높아도 그 반복은 **이전 교수의 습관**이다.
    순서를 뒤집으면 16-18강(반복률 72% · 교수 교체)에서 정확히 틀린 답이 나온다.
    """
    if not stats:
        return "base", "기출 조각이 없다 — 강의록만으로 만든다"
    if mixed_owner:
        # 이 조각의 통계는 다른 강의의 것이다. 남의 반복률로 전략을 정할 수 없다.
        return "base", "이 조각의 주인이 다른 강의라 통계를 이 강의에 적용할 수 없다"
    rate = stats.get("repeat_rate", 0.0)
    if stats.get("professor_changed_2026"):
        return "annotation", f"올해 담당 교수가 바뀌었다 (기출 반복률 {rate:.0%}는 이전 교수의 것)"
    if stats.get("jokbo_weight_hint") == "high":
        return "jokbo", f"교수 유임 · 연도간 반복률 {rate:.0%}"
    return "base", f"교수 유임 · 반복률 {rate:.0%} (높지 않다)"


def slice_for(prep: dict, jokbo_dir: Path, explicit: str | None = None
              ) -> tuple[Path | None, dict, bool]:
    """이 강의의 족보 조각과 그 통계를 찾는다. (조각, stats, 주인이-다른-강의인가)"""
    if explicit:
        p = Path(explicit)
        jk = json.loads(p.read_text(encoding="utf-8"))
        return p, jk.get("stats", {}), bool(jk.get("may_contain"))
    if not (Path(jokbo_dir) / "index.json").exists():
        return None, {}, False
    path, score, top = find_jokbo(prep, Path(jokbo_dir))
    if not path or score < 0.25:
        return None, {}, False
    jk = json.loads(path.read_text(encoding="utf-8"))
    return path, jk.get("stats", {}), top[0][2] is not None


MAX_REPEAT_CLUSTERS = 12       # 프롬프트에 실을 묶음 수. 실측 최대가 13개다(LPRAC)


def repeat_clusters(stats: dict, questions: list | None = None) -> list[dict]:
    """반복 쌍을 묶음으로 잇는다. 쌍 목록보다 묶음이 읽기 쉽다.

    `2020-68 ↔ 2022-55`, `2022-55 ↔ 2023-61`, `2023-61 ↔ 2025-103` 을 쌍으로 늘어놓으면
    같은 것이 세 번 보인다. 이어 붙이면 **한 주제가 다섯 해 반복됐다** 가 한 줄로 선다.

    돌려주는 각 묶음은 `{"members": [최근 연도부터], "stem": 대표 문항의 본문}` 이다.
    """
    parent: dict[str, str] = {}

    def find(x: str) -> str:
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for pair in stats.get("repeat_pairs") or []:
        ra, rb = find(pair["a"]), find(pair["b"])
        if ra != rb:
            parent[ra] = rb

    groups: dict[str, list[str]] = {}
    for k in parent:
        groups.setdefault(find(k), []).append(k)

    stems = {f"{q['year']}-{q['no']}": (q.get("stem") or "") for q in (questions or [])}
    out = []
    for members in groups.values():
        # 연도 내림차순. 대표는 가장 최근 것이다 — 그 해의 문구가 지금 출제자에 가깝다.
        members.sort(key=lambda m: (m.split("-")[0], m), reverse=True)
        stem = next((stems[m] for m in members if stems.get(m)), "")
        out.append({"members": members, "stem": " ".join(stem.split())[:70]})
    out.sort(key=lambda c: (-len(c["members"]), c["members"][0]))
    return out


def topic_count(stats: dict, questions: list | None = None) -> tuple[int, int, int]:
    """(실질 주제 수, 반복 묶음 수, 묶음에 안 든 문항 수).

    기출 파트의 목표 수는 문항 수가 아니라 **이 수**를 상한으로 잡는다. 문항 수로
    잡으면 같은 주제를 다섯 해치 따로 세우게 된다 — 병리학 533문항 중 182개(34%)가
    어떤 묶음에 들어 있고, 묶어서 세면 실질 주제는 420개다.
    """
    clusters = repeat_clusters(stats, questions)
    clustered = sum(len(c["members"]) for c in clusters)
    n = stats.get("n_questions", 0)
    singles = max(n - clustered, 0)
    return len(clusters) + singles, len(clusters), singles


def repeat_block(stats: dict, questions: list | None, stayed: bool) -> str:
    """반복 묶음을 프롬프트에 싣는다.

    **이 블록이 복습 쪽에는 없었다.** `jokbo.py` 가 `repeat_pairs` 를 계산해 두는데
    복습 지침은 `repeat_rate` 숫자 한 줄만 쓰고 쌍 목록을 버렸고, 정작 예습 쪽
    (`prequiz/assemble.py`) 만 그것을 모델에게 보여 주고 있었다. 복습이 예습보다
    기출을 덜 보고 있었던 셈이다.

    관리자가 막아 달라고 명시한 것이 여기 걸린다 — *"겹치는 문제를 너무 반복해서
    풀지 않도록(어 이거 아까 봤던 거네, 선지만 바뀐듯 방지)"*. 병리학 533문항 중
    **182개(34%)가 어떤 묶음에 들어 있다.** 묶어서 세면 실질 주제는 420개다.
    """
    clusters = repeat_clusters(stats, questions)
    if not clusters:
        return ""
    shown = clusters[:MAX_REPEAT_CLUSTERS]
    rows = "".join(f"- {' · '.join(c['members'])}\n"
                   + (f"  「{c['stem']}」\n" if c["stem"] else "")
                   for c in shown)
    more = ("" if len(clusters) == len(shown) else
            f"\n> 묶음 {len(clusters)}개 중 큰 것 {len(shown)}개만 실었다.\n")
    # 쌍 목록 자체가 `jokbo.py` 에서 40개로 잘린다. 잘린 채로 묶으면 묶음이 덜 이어진
    # 것일 수 있으므로, 상한에 닿았을 때만 그렇다고 적는다. 조용히 자르지 않는다.
    cut = ("\n> ⚠ 쌍 목록이 상한(40개)에 닿았다. 위 묶음이 덜 이어졌을 수 있으니\n"
           "> 여기 없는 문항끼리도 겹치는지 직접 보아라.\n"
           if len(stats.get("repeat_pairs") or []) >= 40 else "")
    tail = (
        "**한 묶음은 한 주제다. 각 해의 문항을 따로 카드화하지 마라.** 푸는 사람에게는 "
        "「아까 봤던 건데 선지만 바뀐」 카드로 온다.\n"
        "묶음이 요구한 지식의 **축을 나눠** 3~5장을 내고, `jokbo_ref` 에는 묶음에서 "
        "가장 최근 연도의 문항을 단다. 묶음에 안 든 문항은 1~2장으로 족하다.\n"
        if stayed else
        "**교수가 바뀌었으므로 이 반복은 중요도의 근거가 아니다.** 그래도 묶음은 묶음이다 — "
        "겹치는 문항을 여러 장으로 내면 같은 카드를 두 번 푸는 것이 된다. 한 주제로 묶어라.\n")
    return ("\n### 여러 해 반복된 문항 묶음\n\n"
            "문항 본문의 어휘 겹침으로 코드가 묶었다. 한 줄이 한 주제다.\n\n"
            + rows + more + cut + "\n" + tail)


def jokbo_guidance(stats: dict, title: str, mixed: list | None = None,
                   strategy: str | None = None, shared_bank: bool = False,
                   questions: list | None = None) -> str:
    """전략에 맞는 족보 가중치 지침을 만든다. 전략을 안 주면 통계에서 판정한다."""
    yr = stats.get("professors_by_year") or {}
    rate = stats.get("repeat_rate", 0.0)
    prof_line = " · ".join(f"20{y} {'/'.join(v)}" for y, v in sorted(yr.items(), reverse=True))
    strategy = strategy or decide_strategy(stats, bool(mixed))[0]

    if strategy == "annotation":
        body = (
            "**올해 담당 교수가 바뀌었다.** 과거 기출은 이전 교수의 출제이며, "
            "같은 문항이 다시 나올 것으로 가정하지 마라.\n"
            "기출은 '이 단원에서 무엇이 시험 가능한 지식인가'를 알려주는 신호로만 쓰고, "
            "**강의록의 구조와 올해 필기의 강조점을 우선**한다.\n"
            "필기의 연도가 올해인 항목이 지금 교수가 실제로 강조한 것이다.\n\n"
            "**카드를 어디에 몰 것인가.** 올해 필기가 몰린 슬라이드 → 스탬프·형광펜이 붙은 곳 "
            "→ 강의록이 구조적으로 강조한 곳 순이다. 기출 전용 카드는 만들지 마라 — "
            "기출과 겹치는 내용이면 그것대로 좋지만, 기출을 덮는 것 자체를 목표로 삼지 않는다."
        )
    elif strategy == "jokbo":
        # 교수를 모르는 조각(실습)에서 "교수가 그대로"라고 단언하지 않는다. 아는 만큼만 말한다.
        head = ("**담당 교수가 그대로이고 연도간 문항 반복률이 %.0f%%로 높다.** "
                "이 교수는 기출을 재활용한다.\n" % (rate * 100) if prof_line else
                "**연도간 문항 반복률이 %.0f%%로 높다.** 이 과목은 기출이 재활용된다.\n"
                % (rate * 100))
        body = (
            head +
            "기출이 물은 회수 목표를 **먼저 덮은 뒤** 나머지를 채워라. "
            "반복 출제된 문항은 `importance=core`로 둔다.\n\n"
            "**덮되 나누어 덮어라.** 한 기출 문항이 축을 여럿 물고 있으면 **카드도 여럿으로 나눈다.** "
            "한 장에 몰면 하나만 떠올라도 틀린 카드가 되어 회수를 재지 못한다. "
            "나눌 수 없으면 여러 해 반복된 축만 낸다.\n"
            "**스탬프가 붙었다는 것은 '여기를 보라'이지 '여기를 다 내라'가 아니다.**\n\n"
            "**카드를 어디에 몰 것인가.** 여러 해 반복 출제된 주제에 각 3~5장, "
            "한 해만 나온 기출 주제에 각 1~2장을 먼저 배정하고, 남는 분량으로 "
            "필기·스탬프가 가리키는 곳을 채운다. 기출도 표시도 없는 슬라이드는 목표당 1장을 넘기지 않는다."
        )
    else:
        body = (
            f"담당 교수는 그대로이나 연도간 반복률은 {rate:.0%}로 높지 않다.\n"
            "**강의록을 우선**하고 기출은 우선순위 신호로 쓴다. "
            "교수는 대체로 가르친 데에서 낸다는 것이 기본 가정이다.\n\n"
            "**카드를 어디에 몰 것인가.** 강의록이 구조적으로 강조한 곳(장 제목·요약 슬라이드·"
            "반복 등장하는 개념)을 축으로 잡고, 기출·스탬프·필기가 가리키는 곳을 그 위에 얹는다."
        )
    mix = ""
    if shared_bank:
        # 족보의 실습 문항은 회차 구분 없이 한 덩어리다. 6회 실습이 이 조각 하나를 나눠 쓴다.
        mix += ("\n> ⚠ **이 조각은 실습 전 회차의 문항을 한데 모은 것이다.**\n"
                "> 이번 강의는 그중 한 회차다. **이번 실습 소관 문항만 골라 써라** —\n"
                "> 다른 회차의 문항으로 카드를 만들면 이 덱의 범위를 벗어난다.\n"
                "> 소관 여부는 문항이 다루는 조직·염색·질환이 이번 강의록에 나오는지로 판단한다.\n"
                "> 위의 반복률은 **실습 전체 기준**이다.\n")
    if mixed:
        mix += ("\n> ⚠ **이 조각의 주인은 다른 강의다.** 아래 강의는 족보 본문에 제목이 없어\n"
               "> 문항이 이 섹션으로 흘러들어왔다. **이번 강의 소관 문항을 직접 골라내라.**\n>\n"
               + "".join(f"> - {m['lecture_key']} {m['title']}\n" for m in mixed)
               + ">\n> 위의 담당 교수·반복률은 **주 섹션 기준**이다. 이번 강의에 그대로 적용하지 마라.\n")
    repeats = repeat_block(stats, questions, strategy != "annotation")
    topics, n_cl, n_sg = topic_count(stats, questions)
    return (f"## 이 강의의 전략: `{STRATEGIES[strategy]}`\n\n"
            f"- 조각의 주 섹션: {title}\n"
            f"- 담당 교수: {prof_line or '미상'}\n"
            f"- 연도간 문항 반복률: {rate:.0%} (문항 {stats.get('n_questions', 0)}개)\n"
            f"- 실질 주제 수: **{topics}개** (반복 묶음 {n_cl}개 + 낱개 {n_sg}개)"
            f" — 기출 파트 목표 수의 상한이다\n"
            f"- 족보 가중치 권고: `{stats.get('jokbo_weight_hint', 'normal')}`\n"
            f"{mix}\n{body}\n{repeats}")


def assemble(prep_dir: Path, jokbo_file: Path | None, schema_dir: Path,
             strategy: str | None = None) -> dict:
    prep = json.loads((prep_dir / "prep.json").read_text(encoding="utf-8"))
    prep_md = (prep_dir / "prep.md").read_text(encoding="utf-8")
    contract = (schema_dir / "contract.md").read_text(encoding="utf-8")
    philosophy = (PROMPTS / "philosophy.md").read_text(encoding="utf-8")
    pdf = (prep_dir / prep["annotated_pdf"]).resolve()

    if jokbo_file:
        jk = json.loads(jokbo_file.read_text(encoding="utf-8"))
        jokbo_md = jokbo_file.with_suffix(".md").read_text(encoding="utf-8")
        guidance = jokbo_guidance(jk["stats"], f"{jk['lecture_key']} {jk['title']}",
                                  jk.get("may_contain"), strategy,
                                  shared_bank=jk["lecture_key"] == "PRAC",
                                  questions=jk.get("questions"))
        jokbo_block = (f"# 기출 조각 — {jk['lecture_key']} {jk['title']}\n\n"
                       "이 단원의 과거 기출 전량이다. 정답과 이의제기 답변이 결합돼 있다.\n\n"
                       + jokbo_md.split("\n", 1)[1].lstrip())
    else:
        jk, guidance = None, "## 이 강의의 전략: `기본`\n\n기출 조각이 없다. 강의록과 필기만으로 만든다.\n"
        jokbo_block = ""

    sidecar = "# 슬라이드 사이드카\n\n" + prep_md.split("\n", 1)[1]

    # 단계와 무관한 자료(사이드카·기출)는 따로 낸다. 두 단계가 같은 파일을 다시 읽지 않게 한다.
    ctx_sections = [sidecar] + ([jokbo_block] if jokbo_block else [])
    ctx_files = write_parts(prep_dir, "context", ctx_sections, label="자료 파트")
    ctx_names = [f["name"] for f in ctx_files]

    head = (f"# 강의 → Anki 덱 : {prep['source']}\n\n"
            "너는 이 강의의 시험 대비 Anki 덱을 만든다. 자료는 여기와 아래 지정한 파일에 전부 있다.\n"
            "그 밖의 파일을 찾아다니지 마라.\n\n"
            + read_instructions(pdf, prep["slides"], [prep_dir / n for n in ctx_names],
                                (prep_dir / prep["clean_pdf"]).resolve(),
                                needs_clean(prep))
            + "\n" + guidance)

    out = {"context": ctx_files}
    for stage, task_file, subs in (
        ("plan", "plan.md", {"plan_out": (prep_dir / "plan.json").as_posix()}),
        ("cards", "cards.md", {"plan_in": (prep_dir / "plan.approved.json").as_posix(),
                               "cards_out": (prep_dir / "items.raw.json").as_posix()}),
    ):
        task = (PROMPTS / task_file).read_text(encoding="utf-8")
        for k, v in subs.items():
            task = task.replace("{" + k + "}", v)
        sections = [head, philosophy, task]
        if stage == "cards":
            sections.append(contract)

        out[stage] = write_parts(prep_dir, f"prompt.{stage}", sections, manifest=True)

    out["_pdf_tokens"] = estimate_pdf_tokens(prep)
    out["_jokbo"] = jk
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="완제품 프롬프트를 조립한다")
    ap.add_argument("prep_dir")
    ap.add_argument("--jokbo", help="족보 조각 json. 생략하면 목차 제목으로 자동 대조한다")
    ap.add_argument("--jokbo-dir", default="out/jokbo")
    ap.add_argument("--schema-dir", default="out/schema")
    ap.add_argument("--strategy", default="auto", choices=sorted(STRATEGY_ALIAS),
                    help="족보/필기/기본 중 무엇을 축으로 삼을지. auto 면 통계에서 판정한다")
    args = ap.parse_args(argv)

    prep_dir = Path(args.prep_dir)
    prep = json.loads((prep_dir / "prep.json").read_text(encoding="utf-8"))

    mixed_owner = False
    jokbo_file = Path(args.jokbo) if args.jokbo else None
    if jokbo_file is None and Path(args.jokbo_dir).exists():
        jokbo_file, score, top = find_jokbo(prep, Path(args.jokbo_dir))
        print("족보 조각 자동 대조:")
        for sc, e, via in top:
            mark = " ←선택" if jokbo_file and e["file"] in jokbo_file.name else ""
            label = (f"{e['lecture_key']} {e['title']}" if not via
                     else f"{via['lecture_key']} {via['title']}  (조각은 {e['lecture_key']} 안에 섞여 있음)")
            print(f"   {sc:.2f}  {label}{mark}")
        if score < 0.25:
            print(f"⚠ 일치도가 낮다({score:.2f}). --jokbo 로 직접 지정하는 편이 낫다.")
            jokbo_file = None
        else:
            mixed_owner = top[0][2] is not None

    stats = {}
    if jokbo_file:
        stats = json.loads(jokbo_file.read_text(encoding="utf-8")).get("stats", {})
    strategy = STRATEGY_ALIAS[args.strategy]
    if strategy == "auto":
        strategy, why = decide_strategy(stats, mixed_owner)
    else:
        why = "사람이 --strategy 로 지정했다"

    res = assemble(prep_dir, jokbo_file, Path(args.schema_dir), strategy)

    print(f"\n전략: {STRATEGIES[strategy]}  — {why}")
    if res["_jokbo"]:
        st = res["_jokbo"]["stats"]
        print(f"   족보 가중치 {st['jokbo_weight_hint']} "
              f"· 반복률 {st['repeat_rate']:.0%}"
              f"{' · 교수 교체' if st['professor_changed_2026'] else ''}")
    print()
    ctx_tok = sum(f["tokens"] for f in res["context"])
    for label in ("context", "plan", "cards"):
        files = res[label]
        for f in files:
            warn = "  ⚠ Read 상한 초과" if f["tokens"] > READ_TOKEN_CAP else ""
            print(f"[{label:<7}] {f['name']:<24}{f['chars']:>7,}자 {f['tokens']:>7,}토큰{warn}")
    plan_tok = sum(f["tokens"] for f in res["plan"])
    cards_tok = sum(f["tokens"] for f in res["cards"])
    pdf = res["_pdf_tokens"]
    print(f"\n한 세션에서 ①②를 이어 하면 PDF와 자료는 한 번만 읽는다:")
    print(f"   PDF {pdf:,} + 자료 {ctx_tok:,} + ① {plan_tok:,} + ② {cards_tok:,} "
          f"= 약 {pdf + ctx_tok + plan_tok + cards_tok:,}토큰")
    first = res["plan"][0]["name"]
    print(f"\n   ① {first} 부터 읽혀 {prep_dir}/plan.json 을 받는다")
    print(f"   ② python -m pdf2anki.review {prep_dir}  → 훑고 --approve")
    print(f"   ③ {res['cards'][0]['name']} 를 읽혀 {prep_dir}/items.raw.json 을 받는다")
    return 0


if __name__ == "__main__":
    sys.exit(main())
