"""재현 검사 — `q`만 주고 `a`가 다시 나오는지 본다 (인터뷰 ⓹).

    python -m quiz2.reproduce split runs/<id>     # 1) 푸는 쪽 배치 + 스폰 문구
    #    verify/spawn/answer.bNN.md 마다 서브에이전트를 하나씩, 동시에
    python -m quiz2.reproduce grade runs/<id>     # 2) 채점 쪽 배치 + 스폰 문구
    #    verify/spawn/grade.bNN.md 마다 서브에이전트를 하나씩, 동시에
    python -m quiz2.reproduce score runs/<id>     # 3) 합쳐서 센다

## 왜 이게 규칙이 아니라 검사인가

관리자가 좋은 카드의 기준을 이렇게 말했다.

> *"그냥 AI가 풀었을때 제시된 답과 같은 답이 나올 정도면 만족."*

**v1은 같은 취지를 프롬프트 문장으로만 적었다** — `answer_leak`·`compound_question`
같은 soft 플래그다. 그 실패가 계속 났다. 여기서는 **재는 쪽**으로 옮긴다.

## 푸는 쪽은 답을 못 본다

`verify/asked.bNN.json`에는 `id`·`q`·`card_format`만 들어간다. `a`도 `explanation`도
`slide_no`도 없다. 스폰 문구가 **그 파일 말고는 열지 말라**고 못박는다.

`slide_no`를 뺀 이유가 따로 있다 — 번호를 주면 슬라이드를 찾아가 읽는다. 그러면
자족성을 재는 검사가 아니라 강의록 독해 검사가 된다. Anki 앞면에도 번호는 없다.

**푸는 쪽은 강의록을 안 본다.** 학습자가 앞면을 볼 때 슬라이드를 못 보는 것과 같다.
그래서 이 검사는 두 가지를 한 번에 잰다 — 답이 재현되는가(⓷), 그리고 질문만으로
무엇을 묻는지 알 수 있는가(⑬ 자족성).

## 채점은 코드가 아니라 모델이 한다

*"같은 답"*은 의미 판단이다. 표기가 갈리는 자리가 많다 — `Fibrillin-1` / `FBN1
단백질`, `상염색체 우성` / `autosomal dominant`. 토큰 겹침으로 문턱을 세우면
`coverage_gaps`가 그랬듯 문턱에 붙어 버린다(`RUNS.md`).

그래서 **채점 쪽은 원본 답과 재현 답을 둘 다 보고** 판정한다. 코드는 세기만 한다.

## 아직 안 한 것 — 표시가 카드 뒷면까지 안 간다

③⃝의 결론은 *"표시는 카드 뒷면에 떠야 한다"*였다. `suspects.json`에만 있으면
관리자가 볼 일이 없다.

지금 `--to-card-back`은 `review_note`에 덧붙여 v1 `build.py`의 빨간 박스를 빌려
쓴다. 박스 머리글이 `자료 주의:`라 이름이 안 맞는다. **제 자리는 v2 build가
생길 때다** — `quiz/`는 비교 기준선이라 고치지 않는다.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass

from quiz.cloze import blank_cloze_markup  # noqa: E402

# `blank_cloze_markup`이 내는 HTML을 평문으로 되돌린다. 마스킹 자체는 그 함수에
# 맡긴다 - **Anki 앞면이 가리는 것과 한 글자도 달라지면 안 되기 때문이다.**
_CLOZE_SPAN = '<span class="cloze-blank">[...]</span>'


# 한 배치의 카드 수. 배치를 나누는 이유는 속도가 아니라 **독립**이다 - 1회차에서
# 조각 10개가 한도에 걸려 한 번에 죽었는데 7개는 이미 결과를 쓴 뒤여서 셋만 다시
# 돌리면 됐다(`RUNS.md`). 여기도 같은 값을 노린다.
BATCH_SIZE = 40

VERDICTS = ("same", "partial", "different")

# 카드 뒷면에 덧붙일 때의 상한. build.py의 박스가 800자에서 자른다.
CARD_BACK_MAX = 240


def _text(value) -> str:
    return str(value or "").strip()


def front_text(q: str) -> str:
    """학습자가 앞면에서 실제로 보는 글자. **cloze는 가려서 나간다.**

    안 가리면 답이 `{{c1::...}}` 안에 그대로 실려 나가 검사가 무의미해진다.
    첫 구현이 이걸 놓쳤고 `asked.b*.json`에서 cloze 2장이 답을 들고 있었다.
    """
    return blank_cloze_markup(q or "").replace(_CLOZE_SPAN, "[...]")


def _batches(items: list[dict], size: int) -> list[list[dict]]:
    return [items[i:i + size] for i in range(0, len(items), size)]


def _load_items(run_dir: Path, items_name: str) -> list[dict]:
    payload = json.loads((run_dir / items_name).read_text(encoding="utf-8"))
    return payload["items"] if isinstance(payload, dict) else payload


def _write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")


def _read_batches(verify_dir: Path, stem: str) -> dict[str, dict]:
    """`stem.bNN.json`을 전부 읽어 id → 레코드로 편다. 없는 배치는 조용히 건너뛴다."""
    merged: dict[str, dict] = {}
    for path in sorted(verify_dir.glob(f"{stem}.b*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        for record in (payload.get("items") if isinstance(payload, dict) else payload) or []:
            if _text(record.get("id")):
                merged[_text(record["id"])] = record
    return merged


# ── 1단계: 푸는 쪽 ─────────────────────────────────────────────────────

ANSWER_RULES = """\
## 어떻게 답하나

- **카드 앞면만 보고 답한다.** 강의록도 슬라이드도 안 본다. 그게 이 검사의 요점이다
- 뒷면에 적힐 만한 꼴로 짧게 쓴다. 설명을 늘어놓지 마라
- `cloze`는 `[...]`가 빈칸이다. **빈칸에 들어갈 것**을 답한다. 빈칸이 여럿이면
  나온 순서대로 답한다
- `ox`는 선지마다 O 또는 X를 매긴다
- 확실치 않아도 **아는 데까지 답한다.** 빈칸으로 두지 마라
- 질문만으로 *무엇을 답해야 하는지 자체를* 모르겠으면 `answerable`을 `false`로 하고
  `answer`에는 무엇이 모자란지 한 줄 적는다

## 하지 말 것

- **다른 파일을 열지 마라.** 위에 적힌 그 파일 하나가 전부다.
  `items.*.json`·강의록 PDF·`runs/` 안의 무엇도 열지 않는다.
  **정답이 거기 있고, 보면 이 검사가 무의미해진다**
- 웹을 찾지 마라
- 쓴 뒤에 고쳐 쓰지 마라. 한 번에 완성해서 한 번만 써라
"""


def answer_prompt(asked_path: Path, out_path: Path, count: int) -> str:
    return "\n\n".join([
        f"# 재현 검사 — 카드 {count}장을 푼다",
        "너는 이 강의를 들은 의대생이다. Anki 카드의 **앞면만** 받아서 답한다.\n"
        "이건 카드가 혼자 서는지 재는 검사다. 잘 보이려고 애쓰지 말고 "
        "**앞면만 보고 실제로 떠오르는 답**을 적어라.",
        f"## 읽을 파일\n\n**`{asked_path}`** — 이것 하나뿐이다.",
        ANSWER_RULES,
        f"## 출력\n\n`{out_path}`에 JSON 하나로 쓴다.\n\n"
        "```json\n"
        '{"items": [\n'
        '  {"id": "q001", "answer": "...", "answerable": true}\n'
        "]}\n"
        "```\n\n"
        f"받은 {count}장 **전부**에 대해 한 줄씩 낸다. 빠뜨리지 마라.",
    ])


def split(run_dir: str | Path, items_name: str = "items.checked.json",
          size: int = BATCH_SIZE) -> dict:
    """푸는 쪽에게 줄 배치와 스폰 문구를 만든다. **`a`는 안 나간다.**"""
    run_dir = Path(run_dir)
    verify_dir = run_dir / "verify"
    spawn_dir = verify_dir / "spawn"
    items = _load_items(run_dir, items_name)

    made = []
    for n, batch in enumerate(_batches(items, size), start=1):
        tag = f"b{n:02d}"
        asked_path = verify_dir / f"asked.{tag}.json"
        out_path = verify_dir / f"answered.{tag}.json"
        # 나가는 것은 이 셋뿐이다. slide_no도 card_type도 안 준다.
        _write_json(asked_path, {"batch": tag, "items": [
            {"id": it.get("id"), "q": front_text(it.get("q")),
             "card_format": it.get("card_format") or "basic"}
            for it in batch
        ]})
        spawn_path = spawn_dir / f"answer.{tag}.md"
        spawn_path.parent.mkdir(parents=True, exist_ok=True)
        spawn_path.write_text(answer_prompt(asked_path, out_path, len(batch)),
                              encoding="utf-8")
        made.append({"batch": tag, "count": len(batch), "asked": str(asked_path),
                     "spawn": str(spawn_path), "out": str(out_path)})
    masked = sum(1 for it in items if front_text(it.get("q")) != _text(it.get("q")))
    return {"items": len(items), "masked": masked, "batches": made}


# ── 2단계: 채점 쪽 ─────────────────────────────────────────────────────

GRADE_RULES = """\
## 무엇을 판정하나

관리자가 좋은 카드의 기준을 이렇게 말했다.

> *"그냥 AI가 풀었을때 제시된 답과 같은 답이 나올 정도면 만족."*

그러니 묻는 것은 하나다 — **둘이 같은 답인가.**

    same       같은 답이다. 표기·어순·영한 차이는 같은 답이다
               (`Fibrillin-1` = `FBN1이 만드는 단백질`, `상염색체 우성` = `AD`)
    partial    핵심은 맞는데 항목이 덜 나왔거나 엉뚱한 것이 섞였다
    different  다른 답이다. 재현이 안 됐다

`answerable`이 `false`로 온 것은 **질문만으로 무엇을 묻는지 알 수 없었다**는 뜻이다.
그것도 위 셋으로 판정하되(대개 `different`), `why`에 자족성 문제라고 적어라.

## 하지 말 것

- **원본 답이 의학적으로 옳은지 판정하지 마라.** 그건 다른 검사다.
  여기서 보는 것은 오직 *재현되는가*다
- 원본 답이 틀려 보여도 재현 답이 그와 같으면 `same`이다
- 강의록을 열지 마라. 판정에 필요한 것은 아래 파일에 다 있다
- 쓴 뒤에 고쳐 쓰지 마라. 한 번에 완성해서 한 번만 써라
"""


def grade_prompt(pairs_path: Path, out_path: Path, count: int) -> str:
    return "\n\n".join([
        f"# 재현 검사 채점 — {count}장",
        "카드 앞면(`q`), 카드에 적힌 원본 답(`a`), 그리고 앞면만 보고 다시 푼 답"
        "(`reproduced`)이 온다. 둘이 같은 답인지 판정한다.",
        f"## 읽을 파일\n\n**`{pairs_path}`** — 이것 하나뿐이다.",
        GRADE_RULES,
        f"## 출력\n\n`{out_path}`에 JSON 하나로 쓴다.\n\n"
        "```json\n"
        '{"items": [\n'
        '  {"id": "q001", "verdict": "same", "why": "표기만 다르다"}\n'
        "]}\n"
        "```\n\n"
        f"`why`는 한 줄이다. `same`이면 비워도 된다. 받은 {count}장 **전부** 낸다.",
    ])


def grade(run_dir: str | Path, items_name: str = "items.checked.json",
          size: int = BATCH_SIZE) -> dict:
    """푼 답을 원본과 짝지어 채점 쪽 배치를 만든다."""
    run_dir = Path(run_dir)
    verify_dir = run_dir / "verify"
    spawn_dir = verify_dir / "spawn"
    items = {_text(it.get("id")): it for it in _load_items(run_dir, items_name)}
    answered = _read_batches(verify_dir, "answered")
    if not answered:
        raise SystemExit(f"푼 답이 없다: {verify_dir}/answered.b*.json"
                         f"  (먼저 spawn/answer.*.md를 돌려라)")

    missing = [k for k in items if k not in answered]
    paired = [
        # 채점 쪽도 **푸는 쪽이 본 것과 같은 앞면**을 봐야 판정이 공정하다.
        {"id": k, "q": front_text(items[k].get("q")), "a": items[k].get("a"),
         "reproduced": _text(answered[k].get("answer")),
         "answerable": answered[k].get("answerable", True)}
        for k in items if k in answered
    ]

    made = []
    for n, batch in enumerate(_batches(paired, size), start=1):
        tag = f"b{n:02d}"
        pairs_path = verify_dir / f"pairs.{tag}.json"
        out_path = verify_dir / f"graded.{tag}.json"
        _write_json(pairs_path, {"batch": tag, "items": batch})
        spawn_path = spawn_dir / f"grade.{tag}.md"
        spawn_path.parent.mkdir(parents=True, exist_ok=True)
        spawn_path.write_text(grade_prompt(pairs_path, out_path, len(batch)),
                              encoding="utf-8")
        made.append({"batch": tag, "count": len(batch), "pairs": str(pairs_path),
                     "spawn": str(spawn_path), "out": str(out_path)})
    return {"paired": len(paired), "missing": missing, "batches": made}


# ── 3단계: 세기 ────────────────────────────────────────────────────────

def _card_back_note(record: dict) -> str:
    """뒷면 박스에 덧붙일 한 줄. **판정이 아니라 사실을 적는다.**"""
    reproduced = _text(record.get("reproduced"))
    why = _text(record.get("why"))
    head = ("질문만 주고 다시 풀었을 때 다른 답이 나왔다"
            if record.get("verdict") == "different"
            else "질문만 주고 다시 풀었을 때 일부만 나왔다")
    body = f"재현 검사: {head}"
    if why:
        body += f" — {why}"
    if reproduced:
        body += f" (재현 답: {reproduced})"
    return body[:CARD_BACK_MAX]


def score(run_dir: str | Path, items_name: str = "items.checked.json",
          apply_to: str | None = None, to_card_back: bool = False) -> dict:
    """채점 결과를 합쳐 센다. `apply_to`를 주면 카드에 붙여 새 파일로 쓴다."""
    run_dir = Path(run_dir)
    verify_dir = run_dir / "verify"
    items = _load_items(run_dir, items_name)
    answered = _read_batches(verify_dir, "answered")
    graded = _read_batches(verify_dir, "graded")
    if not graded:
        raise SystemExit(f"채점 결과가 없다: {verify_dir}/graded.b*.json"
                         f"  (먼저 spawn/grade.*.md를 돌려라)")

    records: list[dict] = []
    for item in items:
        card_id = _text(item.get("id"))
        g, a = graded.get(card_id), answered.get(card_id)
        if not g:
            continue
        verdict = _text(g.get("verdict")).lower()
        records.append({
            "id": card_id, "chunk": item.get("chunk"),
            "slide_no": item.get("slide_no"),
            "card_type": item.get("card_type"), "card_format": item.get("card_format"),
            "source_type": item.get("source_type"),
            "verdict": verdict if verdict in VERDICTS else f"unknown({verdict})",
            "answerable": (a or {}).get("answerable", True),
            "why": _text(g.get("why")),
            "q": item.get("q"), "a": item.get("a"),
            "reproduced": _text((a or {}).get("answer")),
        })

    by_verdict = Counter(r["verdict"] for r in records)
    failed = [r for r in records if r["verdict"] in ("partial", "different")]
    report = {
        "lecture_id": items and json.loads(
            (run_dir / "prep.json").read_text(encoding="utf-8"))["lecture_id"],
        "items": len(items),
        "scored": len(records),
        "unscored": [_text(i.get("id")) for i in items
                     if _text(i.get("id")) not in graded],
        "verdicts": dict(by_verdict),
        "unanswerable": sum(1 for r in records if not r["answerable"]),
        "by_card_format": {
            fmt: dict(Counter(r["verdict"] for r in records if r["card_format"] == fmt))
            for fmt in sorted({r["card_format"] for r in records if r["card_format"]})
        },
        "by_chunk": {
            chunk: dict(Counter(r["verdict"] for r in records if r["chunk"] == chunk))
            for chunk in sorted({r["chunk"] for r in records if r["chunk"]})
        },
        "failed": failed,
    }
    _write_json(verify_dir / "report.json", report)

    if apply_to:
        index = {r["id"]: r for r in records}
        out_items = []
        for item in items:
            item = dict(item)
            record = index.get(_text(item.get("id")))
            if record:
                item["reproduce"] = {"verdict": record["verdict"],
                                     "answerable": record["answerable"],
                                     "why": record["why"],
                                     "reproduced": record["reproduced"]}
                if to_card_back and record["verdict"] in ("partial", "different"):
                    # **덮어쓰지 않는다.** 자료 주의(⑳‴)가 이미 적혀 있을 수 있다.
                    existing = _text(item.get("review_note"))
                    note = _card_back_note(record)
                    item["review_note"] = f"{existing}\n{note}" if existing else note
            out_items.append(item)
        _write_json(run_dir / apply_to, {"items": out_items})
        report["applied"] = apply_to

    return report


# ── CLI ────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description="재현 검사 (인터뷰 ⓹)")
    parser.add_argument("stage", choices=["split", "grade", "score"])
    parser.add_argument("run_dir")
    parser.add_argument("--items", default="items.checked.json")
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE)
    parser.add_argument("--apply", default=None,
                        help="score: 결과를 붙여 쓸 파일명 (예: items.reproduced.json)")
    parser.add_argument("--to-card-back", action="store_true",
                        help="score: 실패를 review_note에 덧붙여 뒷면 박스로 보낸다")
    args = parser.parse_args()
    run_dir = Path(args.run_dir)

    if args.stage == "split":
        result = split(run_dir, args.items, args.batch_size)
        print(f"[reproduce/split] 카드 {result['items']}장 → 배치 "
              f"{len(result['batches'])}개. **`a`는 안 나갔다** "
              f"(cloze {result['masked']}장은 빈칸을 가려서 냈다)")
        for b in result["batches"]:
            print(f"  {b['batch']}  {b['count']:>3}장  {b['spawn']}")
        print("\n스폰 문구마다 서브에이전트를 하나씩, 동시에 돌린다.")
        return 0

    if args.stage == "grade":
        result = grade(run_dir, args.items, args.batch_size)
        print(f"[reproduce/grade] 짝지은 것 {result['paired']}장 → 배치 "
              f"{len(result['batches'])}개")
        for b in result["batches"]:
            print(f"  {b['batch']}  {b['count']:>3}장  {b['spawn']}")
        if result["missing"]:
            print(f"  푼 답이 없는 카드 {len(result['missing'])}장: "
                  f"{result['missing'][:10]}")
        return 0

    report = score(run_dir, args.items, args.apply, args.to_card_back)
    total = report["scored"]
    print(f"[reproduce/score] 채점 {total}장 / 카드 {report['items']}장")
    for verdict in VERDICTS:
        n = report["verdicts"].get(verdict, 0)
        pct = f"{100 * n / total:.0f}%" if total else "-"
        print(f"      {verdict:<12}{n:>4}  {pct:>5}")
    unknown = {k: v for k, v in report["verdicts"].items() if k not in VERDICTS}
    if unknown:
        print(f"      알 수 없는 판정: {unknown}")
    print(f"  무엇을 묻는지 모르겠다고 온 것: {report['unanswerable']}장 (자족성)")
    for fmt, counts in report["by_card_format"].items():
        print(f"      {fmt:<8}" + ", ".join(f"{k} {v}" for k, v in counts.items()))
    if report["unscored"]:
        print(f"  채점이 안 된 카드 {len(report['unscored'])}장: {report['unscored'][:10]}")
    if report.get("applied"):
        print(f"  → {report['applied']}에 붙였다"
              + (" (실패는 뒷면 박스로도)" if args.to_card_back else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
