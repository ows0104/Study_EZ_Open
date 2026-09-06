"""카드를 질문만 보고 다시 풀어 본다.

좋은 카드의 최상위 기준은 답의 재현 가능성이고, 그건 문장을 뜯어보는 걸로는 잴 수 없다.
실제로 다시 풀어 봐야 한다. 두 단계로 나눈다.

  1. blind answer   앞면 텍스트만 주고 푼다. 답·해설·슬라이드 번호·원본을 주지 않는다.
  2. semantic grade 원래 답과 재현 답이 의미상 같은지 채점한다. 다만 의학 도메인의
        복원 과거시험은 명백한 원답 오류를 사람 검토 경고로 표시할 수 있다.

**두 단계는 반드시 서로 다른 세션에서 돌린다.** 카드를 만든 세션이 그대로 풀면
이미 답을 아는 상태라 검사가 성립하지 않는다.

두 가지 방법이 있다. 결과는 같은 파일로 모인다.

  자동  solve / judge — 빈 세션(`claude -p`)을 코드가 직접 띄운다. 도구를 다 꺼서
        정답 파일에 접근할 수 없게 한다. 사람 손이 필요 없으니 매번 돌릴 수 있다.
  수동  prepare / grade — 프롬프트를 파일로 내보내 사람이 새 대화에 붙여넣는다.
        자동이 막혔을 때나 결과를 눈으로 따라가고 싶을 때 쓴다.

image_basic / image_occlusion 은 앞면에 그림이 필수라 텍스트만으로는 검사할 수 없다.
검사 대상에서 빼고 그 사실을 기록한다 — 조용히 통과시키지 않는다.

파이프라인에서는 validate 와 build 사이에 선다. build 는 `items.reproduced.json` 을
입력으로 받고, 재현 불가로 갈린 카드가 남아 있으면 덱을 만들지 않는다.

사용:
    python -m pdf2anki.reproduce check   out/lec03     # solve → judge → apply 한 번에
    python -m pdf2anki.reproduce solve   out/lec03     # → reproduce.answers.json (자동)
    python -m pdf2anki.reproduce judge   out/lec03     # → reproduce.grades.json  (자동)
    python -m pdf2anki.reproduce apply   out/lec03     # → items.reproduced.json

    python -m pdf2anki.reproduce prepare out/lec03     # → reproduce.blind.md  (수동, 새 세션에서)
    python -m pdf2anki.reproduce grade   out/lec03     # → reproduce.grade.md  (수동, 또 다른 세션)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import ledger
from .prompting import DEFAULT_DOMAIN, DOMAINS
from .schema import IMAGE_FORMATS
from .session import SessionError, run_blind, verify_blind
from .textutil import answer_runs, norm_key

PROMPTS = Path(__file__).parent / "prompts"
# 프롬프트 파일은 "파일에 써라"라고 지시한다. 자동 모드는 도구가 없으니 stdout 으로 돌린다.
WRITE_TO_FILE = "아래 경로에 이 형태로 쓴다. 다른 말은 덧붙이지 않는다."
WRITE_TO_STDOUT = "아래 형태의 JSON 만 출력한다. 파일에 쓰려 하지 말고, 다른 말도 덧붙이지 않는다."
RE_CLOZE = re.compile(r"\{\{c\d+::(.*?)(?:::(.*?))?\}\}")
# 답이 앞면에 있는 것이 정상이라 누출 검사에서 빼는 형식
LEAK_EXEMPT = {"cloze", "ox"}


def resolved_domain(d: Path, explicit: str | None = None) -> str:
    """Resolve a reproduction domain from CLI, saved run config, or default."""
    if explicit:
        if explicit not in DOMAINS:
            raise ValueError(f"unknown prompt domain: {explicit}")
        return explicit
    for name in ("run.config.json", "prequiz.config.json"):
        path = d / name
        if not path.is_file():
            continue
        try:
            domain = json.loads(path.read_text(encoding="utf-8")).get("domain")
        except (OSError, ValueError):
            continue
        if domain in DOMAINS:
            return domain
    return DEFAULT_DOMAIN


def front_of(card: dict) -> str:
    """실제 Anki 앞면에 보이는 텍스트. cloze 는 실제처럼 가린다."""
    q = card["q"]
    if card["card_format"] == "cloze":
        q = RE_CLOZE.sub(lambda m: f"[...{'|' + m.group(2) if m.group(2) else ''}]", q)
    if card["card_format"] == "ox":
        q = q.rstrip() + "  [O/X]"
    return q.strip()


def assign_ids(cards: list[dict]) -> list[dict]:
    for i, c in enumerate(cards, 1):
        c.setdefault("id", None)
        if not c["id"]:
            c["id"] = f"c{i:03d}"
    return cards


def testable(cards: list[dict]) -> tuple[list[dict], list[dict]]:
    """텍스트만으로 검사할 수 있는 카드와, 그림이 있어야 하는 카드를 가른다."""
    ok = [c for c in cards if c["card_format"] not in IMAGE_FORMATS]
    skipped = [c for c in cards if c["card_format"] in IMAGE_FORMATS]
    return ok, skipped


# 누출 종류별 — 사람에게 하는 말 / 모델에게 시키는 말.
# `run.py` 의 누출 수선이 뒤엣것을 프롬프트에 그대로 싣는다.
LEAK_SAYS = {
    "answer_in_front": "정답이 자기 앞면에 그대로 있다",
    "answer_in_other_front": "정답 용어가 다른 카드 질문에 나온다",
    "explanation_leaked": "해설이 새어 들어갔다",
    "cloze_unmasked": "cloze 정답이 가려지지 않았다",
}
LEAK_FIX = {
    "answer_in_front": "답을 질문에서 빼고 그 지식을 묻는 형태로 다시 세워라. "
                       "기출 선지 목록을 그대로 옮겨 왔다면 목록을 통째로 버려라.",
    "explanation_leaked": "해설이 다른 카드의 앞면에 그대로 들어 있다. 해설을 줄이거나 "
                          "그 카드의 질문을 바꿔라.",
    "cloze_unmasked": "가린 말이 같은 문장 다른 자리에 맨몸으로 또 있다. "
                      "**두 자리를 같은 번호로 가려라** — 한 번호는 함께 열리고 함께 닫힌다.",
}


def crop_texts(d: Path, cards: list[dict]) -> dict[str, str]:
    """그림 카드 앞면의 **그림 안에 인쇄된 글자**. 카드 id → 글자.

    앞면의 정의가 글자에서 멈춰 있었다. 사진 옆에 진단명이 캡션으로 박혀 있으면 앞면이
    답을 인쇄한 채 나가는데, `front_of` 는 `q` 만 보므로 그것을 못 봤다.

    **빌드가 가릴 자리는 빼고 돌려준다.** 가린 것을 또 누출로 세면 수선 고리가 고칠 수
    없는 것을 계속 고치라고 시킨다. 무엇을 가리는지는 `answer_runs` 하나가 정한다 —
    빌드도 같은 함수를 본다.

    `clean.pdf` 나 `prep.json` 이 없으면 빈 값이다. 검사가 없는 것과 통과가 다르므로
    이 경우를 조용히 통과로 만들지 않는다 — 부르는 쪽이 그것을 안다.
    """
    try:
        import fitz
        prep = json.loads((d / "prep.json").read_text(encoding="utf-8"))
        doc = fitz.open(d / "clean.pdf")
    except Exception:
        return {}
    figs = {f["id"]: (p["slide"], f["bbox"])
            for p in (prep.get("pages") or [])
            for f in (p.get("lecture_figures") or [])}
    out: dict[str, str] = {}
    try:
        for c in cards:
            m = c.get("media") or {}
            hit = figs.get(m.get("figure_id"))
            if not hit:
                continue
            slide, bbox = hit
            words = [w[4] for w in doc[slide - 1].get_text("words", clip=fitz.Rect(*bbox))]
            hidden = {i for s, e in answer_runs(words, c.get("a") or "") for i in range(s, e)}
            out[c["id"]] = " ".join(w for i, w in enumerate(words) if i not in hidden)
    finally:
        doc.close()
    return out


def leaks(prompt: str, cards: list[dict],
          crops: dict[str, str] | None = None) -> list[dict]:
    """앞면 묶음에 답·해설이 샜는지 코드가 확인한다. 판정 하나가 레코드 하나다.

    `hard=True` 만 실패다 — **자기 앞면에 자기 답이 있는 경우**.
    한 강의의 카드끼리 용어가 겹치는 것은 당연하므로(A의 정답 용어가 B의 질문에 나오는 등)
    그건 실패가 아니라 참고 사항으로만 센다.

    `crops` 는 그림 안에 인쇄된 글자다. 있으면 그것도 앞면으로 친다.
    """
    out, body = [], norm_key(prompt)
    crops = crops or {}
    for c in cards:
        front = norm_key(front_of(c) + " " + crops.get(c["id"], ""))
        if c["card_format"] not in LEAK_EXEMPT:
            a = norm_key(c["a"])
            if len(a) >= 5 and a in front:
                out.append({"id": c["id"], "kind": "answer_in_front",
                            "hard": True, "detail": c["a"][:60], "card": c})
            elif len(a) >= 6 and a in body:
                out.append({"id": c["id"], "kind": "answer_in_other_front",
                            "hard": False, "detail": c["a"][:24], "card": c})
        exp = (c.get("explanation") or "").strip()
        if len(exp) >= 12 and norm_key(exp) in body:
            out.append({"id": c["id"], "kind": "explanation_leaked",
                        "hard": True, "detail": exp[:60], "card": c})
        if c["card_format"] == "cloze":
            # **힌트 칸은 앞면에서 뺀 뒤에 견준다.** `{{c1::답::갈림}}` 의 셋째 칸은
            # Anki 가 앞면에 보여 주는 힌트이고, 갈림을 보이는 힌트는 정의상 답을 품는다
            # (`자웅{{c1::이체::동체/이체}}`). 그것을 누출로 세면 **의도한 카드가 hard 로
            # 사라진다** — 답이 4글자 이상일 때만 걸려서 짧은 답으로 시험하면 안 보인다
            # (`{{c1::사상유충::간상유충/사상유충}}` 이 걸리고 위의 「이체」는 안 걸렸다).
            #
            # 힌트가 답을 지나치게 알려 주는 것은 다른 문제이고, 그 판단은 저작 쪽
            # 철학이 맡는다. 여기서 보는 것은 **가린 말이 문장 본문에 맨몸으로 또
            # 있는가** 하나다.
            bare = norm_key(RE_CLOZE.sub(lambda m: "[...]", c["q"]))
            for m in RE_CLOZE.finditer(c["q"]):
                hidden = norm_key(m.group(1))
                if len(hidden) >= 4 and hidden in bare:
                    out.append({"id": c["id"], "kind": "cloze_unmasked",
                                "hard": True, "detail": m.group(1)[:30], "card": c})
    return out


def check_no_leak(prompt: str, cards: list[dict]) -> tuple[list[str], list[str]]:
    """`leaks` 를 사람이 읽는 줄로 바꾼 것. 판정은 `leaks` 가 한다."""
    hard, soft = [], []
    for x in leaks(prompt, cards):
        s = f"{x['id']}: {LEAK_SAYS[x['kind']]}"
        if x["kind"] != "explanation_leaked":
            s += f" ({x['detail']!r})"
        (hard if x["hard"] else soft).append(s)
    return hard, soft


def hard_leaks(d: Path) -> list[dict]:
    """폴더 하나의 하드 누출. `run.py` 의 누출 수선 고리가 쓴다.

    누출 검사는 풀이 **전**에 도는 결정론적 검사라 세션도 돈도 들지 않는다.
    그래서 수선 고리를 앞에 놓을 수 있다.
    """
    cards = load_cards(d)
    ok, _ = testable(cards)
    # 앞면 묶음(`body`)은 텍스트 카드로 만든다 — 풀이자가 실제로 받는 것이 그것이다.
    # 그러나 **누출은 그림 카드에서도 난다.** 형식으로 제외하던 것을 여기서 되돌린다.
    return [x for x in leaks(build_blind(d, ok, None), cards, crop_texts(d, cards))
            if x["hard"]]


def task_text(name: str, out_path: Path | None) -> str:
    """프롬프트를 읽고 출력 지시를 파일/stdout 중 하나로 맞춘다."""
    task = (PROMPTS / name).read_text(encoding="utf-8")
    if out_path is not None:
        return task.replace("{out}", out_path.as_posix())
    if WRITE_TO_FILE in task:
        task = task.replace(WRITE_TO_FILE, WRITE_TO_STDOUT)
    else:  # 프롬프트 문구가 바뀌었으면 조용히 넘어가지 말고 덧붙여서라도 알린다
        task += f"\n\n{WRITE_TO_STDOUT}\n"
    return task.replace("{out}", "").rstrip() + "\n"


def build_blind(d: Path, cards: list[dict], out_path: Path | None,
                domain: str | None = None) -> str:
    lines = [f"| {c['id']} | {front_of(c)} |" for c in cards]
    table = "\n".join(["| id | 앞면 |", "|---|---|"] + lines)
    task = task_text("reproduce_answer.md", out_path)
    domain = resolved_domain(d, domain)
    knowledge = ("일반적인 의학 지식" if domain == "medical_ko"
                 else "일반적인 해당 분야 지식")
    task = task.replace("{domain_knowledge}", knowledge)
    return f"{task}\n\n---\n\n# 카드 {len(cards)}장\n\n{table}\n"


def numbered_front(card: dict) -> str:
    """빈칸을 `[1]`·`[2]` 로 번호 붙여 그린 앞면. 힌트가 있으면 힌트도 함께 보인다.

    `front_of` 는 전부 `[...]` 로 그려서 **어느 빈칸을 말하는지 가리킬 수가 없다.**
    축 검사는 빈칸마다 판정을 받아야 하므로 번호가 필요하다.
    """
    n = [0]

    def one(m):
        n[0] += 1
        hint = m.group(2)
        return f"[{n[0]}{'|' + hint if hint else ''}]"

    return RE_CLOZE.sub(one, card["q"]).strip()


def build_axis(cards: list[dict], out_path: Path | None) -> str:
    lines = [f"| {c['id']} | {numbered_front(c)} |" for c in cards]
    table = "\n".join(["| id | 앞면 |", "|---|---|"] + lines)
    task = task_text("reproduce_axis.md", out_path)
    return f"{task}\n\n---\n\n# 카드 {len(cards)}장\n\n{table}\n"


def load_cards(d: Path) -> list[dict]:
    """id 를 확정해 되쓴다. 이후 단계가 전부 id 로 짝을 맞추기 때문이다."""
    src = d / "items.checked.json"
    cards = assign_ids(json.loads(src.read_text(encoding="utf-8"))["cards"])
    src.write_text(json.dumps({"cards": cards}, ensure_ascii=False, indent=2), encoding="utf-8")
    return cards


def cmd_prepare(d: Path, *, domain=None, **_) -> int:
    cards = load_cards(d)
    ok, skipped = testable(cards)
    text = build_blind(d, ok, d / "reproduce.answers.json", domain)

    hard, soft = check_no_leak(text, ok)
    out = d / "reproduce.blind.md"
    if hard:
        print("누출 검사 실패 — 자기 앞면에 정답이 있다:")
        for p in hard:
            print(f"   {p}")
        return 1
    out.write_text(text, encoding="utf-8")
    print(f"검사 대상 {len(ok)}장 · 그림 카드라 제외 {len(skipped)}장")
    print("누출 검사 통과 (자기 앞면에 정답·해설 없음, 슬라이드 번호 없음)")
    if soft:
        print(f"참고: 정답 용어가 다른 카드 질문에 나오는 경우 {len(soft)}건 — "
              "한 강의 안에서는 불가피하다")
        for p in soft[:5]:
            print(f"   {p}")
    print(f"\n→ {out}")
    print("   **반드시 새 세션에서 열어라.** 이 세션은 이미 답을 알고 있어 검사가 성립하지 않는다.")
    return 0


def grade_rows(d: Path) -> list[tuple[str, str]]:
    """(id, 채점 항목 본문) 목록. 답이 없는 카드는 채점 대상이 아니다."""
    cards = {c["id"]: c for c in assign_ids(json.loads(
        (d / "items.checked.json").read_text(encoding="utf-8"))["cards"])}
    ans_path = d / "reproduce.answers.json"
    if not ans_path.exists():
        raise FileNotFoundError(ans_path)
    answers = json.loads(ans_path.read_text(encoding="utf-8"))["answers"]

    rows = []
    for a in answers:
        c = cards.get(a["id"])
        if not c:
            continue
        answerable = a.get("answerable", True)
        rep = a.get("answer", "").strip() if answerable else ""
        note = "" if answerable else f" (풀 수 없음: {a.get('why_not', '')})"
        # 출처를 실어 보낸다. 기본 채점은 의미 비교만 하지만, 도메인과 출처가 허용하면
        # 복원 정답을 사람 검토 경고로 표시할 수 있다. 해설은 어느 해 정답인지, 교수가
        # 무엇을 인정했는지 같은 근거를 제공해 단순한 교과서 차이를 오판하지 않게 한다.
        # 채점은 원래 답을 보고 하는 단계라 답이 새지도 않는다.
        expl = (c.get("explanation") or "").strip()
        rows.append((a["id"],
                     f"### {a['id']}\n- 출처: {c['source_type']}\n"
                     f"- 질문: {front_of(c)}\n- 원래 답: {c['a']}\n"
                     + (f"- 카드의 해설: {expl}\n" if expl else "")
                     + f"- 재현 답: {rep or '(없음)'}{note}"))
    return rows


def build_grade(rows: list[tuple[str, str]], out_path: Path | None,
                domain: str = DEFAULT_DOMAIN) -> str:
    task = task_text("reproduce_grade.md", out_path)
    if domain == "medical_ko" and any("- 출처: jokbo\n" in row for _, row in rows):
        task += "\n\n" + (PROMPTS / "adapters" / "medical_past_exam_grade.md").read_text(
            encoding="utf-8").strip()
    body = "\n\n".join(r for _, r in rows)
    return f"{task}\n\n---\n\n# 채점 대상 {len(rows)}장\n\n{body}\n"


def cmd_grade(d: Path, *, domain=None, **_) -> int:
    try:
        rows = grade_rows(d)
    except FileNotFoundError as e:
        print(f"{e} 가 없다. solve 를 돌리거나 reproduce.blind.md 를 새 세션에서 먼저 풀어라.")
        return 1
    out = d / "reproduce.grade.md"
    out.write_text(build_grade(rows, d / "reproduce.grades.json",
                               resolved_domain(d, domain)), encoding="utf-8")
    print(f"채점 대상 {len(rows)}장 → {out}")
    print("   이것도 새 세션에서 돌리는 편이 낫다 (푼 세션은 자기 답을 옹호하기 쉽다).")
    return 0


def chunks(seq: list, size: int) -> list[list]:
    if size <= 0 or size >= len(seq):
        return [seq]
    return [seq[i:i + size] for i in range(0, len(seq), size)]


def run_chunks(batches: list[list], build, key: str, ids_of, *,
               model=None, timeout=1800, retries=1, label="", jobs=4,
               out: Path | None = None) -> list[dict]:
    """묶음마다 빈 세션을 하나씩 띄운다. 묶음이 다르면 세션도 다르다.

    묶음끼리는 완전히 독립이라 **동시에 돌린다.** 순서가 결과에 영향을 주지 않는다 —
    답도 채점도 카드 id 로 짝을 맞추기 때문이다.

    한 세션이 통째로 실패해도 나머지는 살린다. 빠진 카드는 조용히 사라지지 않고
    호출한 쪽에서 누락으로 잡힌다.
    """
    def one(n: int, batch: list) -> tuple[list, float, dict, str]:
        want = {ids_of(x) for x in batch}
        tag = f"{label} {n}/{len(batches)}"
        prompt = build(batch)
        used = {}
        for attempt in range(retries + 1):
            try:
                data, info = run_blind(prompt, model=model, timeout=timeout, label=tag)
                ledger.add(used, info.get("usage"))     # 실패한 시도의 토큰도 실제로 썼다
                rows = [r for r in data.get(key, []) if isinstance(r, dict) and "id" in r]
                if not rows:
                    raise SessionError(f"{key} 가 비어 있다")
                extra = {r["id"] for r in rows} - want
                miss = want - {r["id"] for r in rows}
                note = []
                if miss:
                    note.append(f"빠짐 {len(miss)}")
                if extra:
                    note.append(f"모르는 id {len(extra)}")
                return ([r for r in rows if r["id"] in want],
                        info.get("cost_usd") or 0.0, used,
                        f"  {tag}  {len(batch)}장 → {len(rows)}건"
                        + (f"  ({', '.join(note)})" if note else ""))
            except SessionError as e:
                if attempt >= retries:
                    return [], 0.0, used, f"  {tag}  포기한다 — {e}"
        return [], 0.0, used, f"  {tag}  실패"

    t0 = time.time()
    got, cost, used = [], 0.0, {}
    with ThreadPoolExecutor(max_workers=max(1, jobs)) as pool:
        futures = [pool.submit(one, n, b) for n, b in enumerate(batches, 1)]
        for f in futures:                      # 제출 순서대로 읽어 출력 순서를 지킨다
            rows, c, u, line = f.result()
            got += rows
            cost += c
            ledger.add(used, u)
            print(line)
    if cost:
        print(f"  비용 ${cost:.3f} · 토큰 {ledger.total(used):,}")
    if out is not None:
        # 세션을 동시에 돌렸으므로 벽시계 시간은 합이 아니다. 있는 그대로 적는다.
        ledger.append(out, label or "빈세션", seconds=time.time() - t0,
                      cost=cost, usage=used, sessions=len(batches))
    return got


def canary(d: Path, model, skip: bool, quiet: bool = False) -> bool:
    """돌리기 전에 눈가리개가 실제로 붙어 있는지 잰다."""
    if skip:
        print("  차단 확인 완료 (앞 단계에서 쟀다)" if quiet
              else "차단 검사를 건너뛴다 (--skip-canary). 결과를 그만큼 덜 믿어라.")
        return True
    ok, msg = verify_blind(d / "items.checked.json", model=model)
    print(("  " if ok else "") + msg)
    return ok


def merge_by_id(path: Path, key: str, rows: list[dict]) -> list[dict]:
    """기존 결과에 새 결과를 id 기준으로 덮어쓴다. 부분 재검사가 나머지를 지우지 않게 한다."""
    old = []
    if path.exists():
        old = json.loads(path.read_text(encoding="utf-8")).get(key, [])
    fresh = {r["id"] for r in rows}
    return [r for r in old if r["id"] not in fresh] + rows


def cmd_solve(d: Path, *, model=None, chunk=25, timeout=1800, retries=1, force=False,
              skip_canary=False, canary_done=False, only=None, jobs=4,
              domain=None, **_) -> int:
    out = d / "reproduce.answers.json"
    if out.exists() and not force and not only:
        print(f"{out} 가 이미 있다. 다시 풀려면 --force 를 줘라.")
        return 1
    cards = load_cards(d)
    ok, skipped = testable(cards)
    if only:
        ok = [c for c in ok if c["id"] in only]
        if not ok:
            print(f"--only 에 해당하는 검사 대상 카드가 없다: {sorted(only)}")
            return 1

    # 자동이라고 누출 검사를 건너뛰지 않는다. 새는 프롬프트로는 뭘 재도 의미가 없다.
    domain = resolved_domain(d, domain)
    hard, soft = check_no_leak(build_blind(d, ok, None, domain), ok)
    if hard:
        print("누출 검사 실패 — 자기 앞면에 정답이 있다:")
        for p in hard:
            print(f"   {p}")
        return 1

    if not canary(d, model, skip_canary or canary_done, quiet=canary_done):
        return 1

    batches = chunks(ok, chunk)
    print(f"검사 대상 {len(ok)}장 · 그림 카드라 제외 {len(skipped)}장 · 세션 {len(batches)}개")
    print("누출 검사 통과. 각 세션은 이력·프로젝트 파일·도구 없이 앞면 텍스트만 본다.")
    answers = run_chunks(batches, lambda b: build_blind(d, b, None, domain), "answers",
                         lambda c: c["id"], model=model, timeout=timeout,
                         retries=retries, label="풀이", jobs=jobs, out=d)

    seen = {a["id"] for a in answers}
    missing = [c["id"] for c in ok if c["id"] not in seen]
    if not answers:
        print("한 장도 받지 못했다. 아무것도 쓰지 않는다.")
        return 1
    out.write_text(json.dumps({"answers": merge_by_id(out, "answers", answers)},
                              ensure_ascii=False, indent=2), encoding="utf-8")
    unans = [a for a in answers if not a.get("answerable", True)]
    print(f"\n푼 카드 {len(answers)}장 · 풀 수 없다고 표시 {len(unans)}장"
          + (f" · 응답 누락 {len(missing)}장" if missing else ""))
    if missing:
        print(f"   누락 {', '.join(missing[:10])} — 다시 돌리면 채워진다")
    print(f"→ {out}")
    return 0


def cmd_axis(d: Path, *, model=None, chunk=25, timeout=1800, retries=1,
             force=False, jobs=4, **_) -> int:
    """**빈칸이 무엇을 묻는지** 빈 세션에게 물어 ① 위반을 센다.

    풀이(`cmd_solve`)는 「답이 뭐냐」를 묻는데, `cloze` 는 앞면에 문장이 있어서
    **나쁜 빈칸일수록 잘 풀린다** — 그럴듯한 것을 채워 넣을 수 있기 때문이다.
    2026-09-06 `260901_01` v6 에서 관리자가 「별로」라고 판정한 카드가
    (`선충류는 [ ], 흡충류는 [ ], 조충류는 [ ]이다`) 재현·검증·soft flag 를
    **전부 깨끗이 지났다.** 그래서 다른 것을 묻는 세션을 따로 둔다.

    답을 맞히라고 하지 않으므로 **정답 누출이 원리적으로 없다** — 앞면만 준다.
    """
    out = d / "reproduce.axis.json"
    if out.exists() and not force:
        print(f"{out} 가 이미 있다. 다시 재려면 --force 를 줘라.")
        return 1
    cards = [c for c in load_cards(d) if c.get("card_format") == "cloze"]
    if not cards:
        print("빈칸 카드가 없다. 잴 것이 없다.")
        out.write_text(json.dumps({"axes": []}, ensure_ascii=False, indent=2), encoding="utf-8")
        return 0

    batches = chunks(cards, chunk)
    print(f"빈칸 카드 {len(cards)}장 · 세션 {len(batches)}개")
    rows = run_chunks(batches, lambda b: build_axis(b, None), "axes",
                      lambda c: c["id"], model=model, timeout=timeout,
                      retries=retries, label="축 검사", jobs=jobs, out=d)
    if not rows:
        print("한 장도 받지 못했다. 아무것도 쓰지 않는다.")
        return 1
    out.write_text(json.dumps({"axes": merge_by_id(out, "axes", rows)},
                              ensure_ascii=False, indent=2), encoding="utf-8")

    by_id = {c["id"]: c for c in cards}
    bad = [r for r in rows if any(not b.get("told", True) for b in r.get("blanks", []))]
    n_blank = sum(len(r.get("blanks", [])) for r in rows)
    n_bad = sum(1 for r in rows for b in r.get("blanks", []) if not b.get("told", True))
    print(f"\n빈칸 {n_blank}개 중 축을 못 댄 것 {n_bad}개 · 그런 카드 {len(bad)}장")
    for r in bad:
        c = by_id.get(r["id"])
        print(f"   [{r['id']}] {numbered_front(c) if c else ''}")
        for b in r.get("blanks", []):
            if not b.get("told", True):
                print(f"      [{b.get('n')}] {b.get('why_not', '')[:90]}")
    print(f"→ {out}")
    return 0


def cmd_judge(d: Path, *, model=None, judge_model="sonnet", chunk=25, timeout=1800,
              retries=1, force=False, skip_canary=False, canary_done=False,
              only=None, jobs=4, domain=None, **_) -> int:
    out = d / "reproduce.grades.json"
    if out.exists() and not force and not only:
        print(f"{out} 가 이미 있다. 다시 채점하려면 --force 를 줘라.")
        return 1
    try:
        rows = grade_rows(d)
    except FileNotFoundError as e:
        print(f"{e} 가 없다. solve 를 먼저 돌려라.")
        return 1
    if only:
        rows = [r for r in rows if r[0] in only]
        if not rows:
            print(f"--only 에 해당하는 채점 대상이 없다: {sorted(only)}")
            return 1
    domain = resolved_domain(d, domain)
    # 기본 과제는 의미 비교다. 의학+족보 항목의 answer_suspect도 자동 판정이 아니라
    # 명백한 경우에만 남기는 검토 경고이므로 별도 수정 권한을 주지 않는다.
    model = model or judge_model

    if not canary(d, model, skip_canary or canary_done, quiet=canary_done):
        return 1

    batches = chunks(rows, chunk)
    print(f"채점 대상 {len(rows)}장 · 세션 {len(batches)}개")
    grades = run_chunks(batches, lambda b: build_grade(b, None, domain), "grades",
                        lambda r: r[0], model=model, timeout=timeout,
                        retries=retries, label="채점", jobs=jobs, out=d)
    if not grades:
        print("한 건도 받지 못했다. 아무것도 쓰지 않는다.")
        return 1
    out.write_text(json.dumps({"grades": merge_by_id(out, "grades", grades)},
                              ensure_ascii=False, indent=2), encoding="utf-8")
    tally = Counter(g.get("verdict") for g in grades)
    print(f"\n채점 {len(grades)}건  {dict(tally)}")
    print(f"→ {out}\n   다음: python -m pdf2anki.reproduce apply {d.as_posix()}")
    return 0


def cmd_apply(d: Path, **_) -> int:  # apply 는 항상 전체를 훑는다 (--only 무시)
    # validate 가 items.checked.json 을 다시 쓰면 id 가 지워진다. 여기서 다시 매긴다 —
    # 순서가 같으면 같은 id 가 나오므로 앞서 받은 답·채점과 그대로 짝이 맞는다.
    cards = assign_ids(json.loads((d / "items.checked.json").read_text(encoding="utf-8"))["cards"])
    gpath = d / "reproduce.grades.json"
    if not gpath.exists():
        print(f"{gpath} 가 없다. judge 를 돌리거나 reproduce.grade.md 를 새 세션에서 먼저 채점해라.")
        return 1
    grades = {g["id"]: g for g in json.loads(gpath.read_text(encoding="utf-8"))["grades"]}
    answers = {}
    apath = d / "reproduce.answers.json"
    if apath.exists():
        answers = {a["id"]: a for a in json.loads(apath.read_text(encoding="utf-8"))["answers"]}

    stat = Counter()
    for c in cards:
        g, a = grades.get(c["id"]), answers.get(c["id"], {})
        if c["card_format"] in IMAGE_FORMATS:
            c["reproduce"] = {"status": "skipped", "why": "앞면에 그림이 필요해 텍스트만으로 검사 불가"}
            stat["skipped"] += 1
            continue
        if not g:
            c["reproduce"] = {"status": "not_run"}
            stat["not_run"] += 1
            continue
        # 구조화해서 붙인다. review_note 문자열에 섞지 않는다.
        c["reproduce"] = {"status": "graded", "verdict": g["verdict"],
                          "reason": g.get("reason"), "note": g.get("note"),
                          "answerable": a.get("answerable", True),
                          "confidence": a.get("confidence"),
                          "reproduced_answer": a.get("answer", "")}
        stat[g["verdict"]] += 1
        if g.get("reason"):
            stat["reason:" + g["reason"]] += 1

    out = d / "items.reproduced.json"
    out.write_text(json.dumps({"cards": cards}, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"판정  same {stat['same']} · partial {stat['partial']} · different {stat['different']}"
          f" · 그림카드 제외 {stat['skipped']} · 미실행 {stat['not_run']}")
    reasons = {k[7:]: v for k, v in stat.items() if k.startswith("reason:")}
    if reasons:
        print(f"갈린 이유  {reasons}")
        print("   question_ambiguous · needs_options · answer_underspecified → 카드 결함")
        print("   lecture_specific · genuinely_wrong                        → 카드 결함 아님")
        print("   answer_suspect  → 기출 정답 쪽을 의심한 것. 막지 않고 카드 뒷면에 띄운다")
    n_sus = sum(1 for c in cards if (c.get("reproduce") or {}).get("reason") == "answer_suspect")
    if n_sus:
        print(f"\n정답 의심 {n_sus}장 (기출 복원본의 정답을 의학 지식으로 되짚은 것):")
        for c in cards:
            r = c.get("reproduce") or {}
            if r.get("reason") == "answer_suspect":
                print(f"   {c['q'][:60]}")
                print(f"      원래 {c['a'][:36]!r} · {(r.get('note') or '')[:60]}")
    bad = [c for c in cards
           if (c.get("reproduce") or {}).get("reason")
           in ("question_ambiguous", "needs_options", "answer_underspecified")]
    if bad:
        print(f"\n고쳐야 할 카드 {len(bad)}장:")
        for c in bad[:12]:
            r = c["reproduce"]
            print(f"   [{r['reason']}] {c['q'][:64]}")
            print(f"      원래 {c['a'][:40]!r}  →  재현 {r['reproduced_answer'][:40]!r}")
    print(f"\n→ {out}")
    return 0


def cmd_check(d: Path, **kw) -> int:
    """solve → judge → apply. 파이프라인에서 쓰는 한 칸.

    --only 를 주면 그 카드만 다시 풀고 채점한다. 나머지 카드의 결과는 그대로 살아 있고,
    apply 는 늘 전체를 대상으로 돌아 items.reproduced.json 을 완전한 상태로 만든다.
    """
    for name, fn in (("풀이", cmd_solve), ("채점", cmd_judge), ("반영", cmd_apply)):
        print(f"\n── {name}")
        rc = fn(d, **kw)
        if rc:
            print(f"{name} 단계에서 멈췄다.")
            return rc
        kw = {**kw, "canary_done": True}   # 카나리아는 한 번만 확인하면 된다
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="질문만 보고 다시 풀어 카드를 검사한다")
    ap.add_argument("step", choices=["check", "solve", "judge", "apply", "prepare",
                                 "grade", "axis"])
    ap.add_argument("prep_dir")
    ap.add_argument("--model", help="빈 세션에 쓸 모델 (예: opus, sonnet). 생략하면 CLI 기본값")
    ap.add_argument("--chunk", type=int, default=25,
                    help="한 세션에 넣을 카드 수. 0 이면 전부 한 번에 (기본 25)")
    ap.add_argument("--timeout", type=int, default=1800, help="세션 하나의 제한 시간(초)")
    ap.add_argument("--retries", type=int, default=1, help="세션 실패 시 재시도 횟수")
    ap.add_argument("--force", action="store_true", help="이미 있는 결과 파일을 덮어쓴다")
    ap.add_argument("--judge-model", default="sonnet",
                    help="채점에 쓸 모델. 의미 비교라 작은 모델로 충분하다 (기본 sonnet). "
                         "--model 을 주면 그쪽이 이긴다")
    ap.add_argument("--jobs", type=int, default=4, help="동시에 띄울 빈 세션 수")
    ap.add_argument("--only", help="이 카드들만 다시 검사한다 (id 쉼표 구분). "
                                   "결과는 기존 파일에 덮어써 합쳐진다")
    ap.add_argument("--skip-canary", action="store_true",
                    help="빈 세션이 정말 파일을 못 읽는지 미리 재 보는 검사를 건너뛴다")
    ap.add_argument("--domain", choices=sorted(DOMAINS),
                    help=f"퀴즈 도메인 정책 (기본: 실행 설정 또는 {DEFAULT_DOMAIN})")
    args = ap.parse_args(argv)
    d = Path(args.prep_dir)
    if not d.is_dir():
        print(f"{d} 가 없다.")
        return 1
    fn = {"check": cmd_check, "solve": cmd_solve, "judge": cmd_judge, "apply": cmd_apply,
          "prepare": cmd_prepare, "grade": cmd_grade, "axis": cmd_axis}[args.step]
    only = {x.strip() for x in args.only.split(",") if x.strip()} if args.only else None
    domain = resolved_domain(d, args.domain)
    return fn(d, model=args.model, judge_model=args.judge_model, chunk=args.chunk,
              timeout=args.timeout, retries=args.retries, force=args.force,
              skip_canary=args.skip_canary, only=only, jobs=args.jobs, domain=domain)


if __name__ == "__main__":
    sys.exit(main())
