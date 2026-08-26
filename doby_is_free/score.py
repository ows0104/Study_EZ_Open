"""이미지 카드에 사진이 정말 필요한지 잰다 — 어느 덱이 만들었든 같은 자로.

`pdf2anki` 의 재현검사(`reproduce`)는 이미지 카드를 **검사에서 뺀다**. 앞면에 그림이
있어야 성립하는 카드를 텍스트만으로 풀릴 수 없다고 보기 때문이다. 그래서 이미지
카드는 지금 아무 검사도 받지 않는다.

그런데 그냥 텍스트만 주고 켜면 더 나쁘다. **누출된 카드일수록 잘 풀리기 때문이다.**
「편심성 핵과 핵주위 halo가 보이는 이 세포는?」은 사진 없이도 맞는다. 그 검사는
누출을 걸러 내는 게 아니라 누출에 상을 준다.

그래서 두 번 푼다.

    A  질문 + 사진    →  맞아야 한다.  못 맞히면 카드가 성립하지 않는 것이다.
    B  질문만         →  틀려야 한다.  맞으면 사진이 장식이다.

    A O  B X   image_required     사진이 일한다
    A O  B O   image_decorative   사진을 가려도 풀린다 (결함)
    A X  B X   unanswerable       사진을 줘도 못 푼다
    A X  B O   inconsistent       채점이 흔들린 것. 사람이 본다

푸는 세션은 정답을 볼 수 없다. B 는 도구가 아예 없고(`session.run_blind`), A 는
그림만 있는 빈 폴더에서 `Read` 만 갖는다 — 정답 파일이 그 폴더에 없다.

**이 자는 아직 사람 판정과 맞춰 본 적이 없다.** 260818_01 두 덱을 눈으로 읽고 센
값은 우리 37장 중 22장이 장식, GPT 46장 중 6장이 장식이었다. 이 코드가 그 근처를
내놓는지부터 확인해야 자로 쓸 수 있다.

사용:
    python -m doby_is_free.score <apkg> [<apkg> ...] -o out/score
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from pdf2anki import ledger, session

from .deck import Deck, Note, load

BATCH_WITH_IMAGE = 20
BATCH_TEXT_ONLY = 40


# ─────────────────────────────────────────────────────── 눈만 뜬 세션

def run_with_eyes(prompt: str, cwd: Path, *, model: str | None = None,
                  timeout: int = 1800, label: str = "") -> tuple[dict, dict]:
    """그림은 볼 수 있고 그 밖은 못 보는 세션.

    `run_blind` 는 `Read` 까지 끄기 때문에 사진을 줄 수 없다. 여기서는 `Read` 만
    열되 **작업 폴더에 그림 말고는 아무것도 두지 않는다.** 설정도 읽지 않는다
    (`--setting-sources ""`) — 프로젝트 규칙이 딸려 들어오면 조건이 달라진다.
    """
    exe = shutil.which("claude")
    if not exe:
        raise session.SessionError("claude CLI 를 찾지 못했다.")
    argv = [exe, "-p", "--output-format", "json",
            "--setting-sources", "",
            "--allowed-tools", "Read,Glob",
            "--disallowed-tools", "Bash,Write,Edit,WebFetch,WebSearch,Task,Agent",
            "--add-dir", str(cwd.resolve())]
    if model:
        argv += ["--model", model]
    try:
        proc = subprocess.run(argv, input=prompt, cwd=str(cwd), timeout=timeout,
                              capture_output=True, text=True,
                              encoding="utf-8", errors="replace")
    except subprocess.TimeoutExpired:
        raise session.SessionError(f"{label}: {timeout}초 안에 끝나지 않았다")
    if proc.returncode != 0:
        raise session.SessionError(
            f"{label}: claude 가 {proc.returncode} 로 끝났다\n"
            f"{(proc.stderr or proc.stdout or '').strip()[-400:]}")
    try:
        env = json.loads(proc.stdout)
        body = env["result"]
    except (json.JSONDecodeError, KeyError, TypeError):
        env, body = {}, proc.stdout
    if env.get("is_error"):
        raise session.SessionError(f"{label}: {str(body)[:400]}")
    return session.extract_json(body), {
        "cost_usd": env.get("total_cost_usd"), "usage": ledger.usage_of(env)}


# ─────────────────────────────────────────────────────────── 프롬프트

ASK = """아래 문제들에 답해라. 각 문제는 서로 무관하다.

{items}

답만 짧게 적어라. 모르면 "모르겠다" 라고 적어라 — 지어내지 마라.
JSON 하나로만 답해라: {{"answers": [{{"i": 1, "a": "..."}}]}}
"""

ASK_IMAGE = """아래 문제들에 답해라. 각 문제는 서로 무관하고, 문제마다 사진이 하나씩 있다.
**사진을 반드시 읽고 답해라.** 사진 파일은 이 폴더에 있다.

{items}

답만 짧게 적어라. 모르면 "모르겠다" 라고 적어라 — 지어내지 마라.
JSON 하나로만 답해라: {{"answers": [{{"i": 1, "a": "..."}}]}}
"""

GRADE = """카드의 원래 정답과, 다른 사람이 그 질문에 답한 것을 비교해라.
**표현이 달라도 같은 것을 가리키면 맞다.** 한국어/영어, 약어/전체 이름, 부연의
많고 적음은 차이로 보지 않는다. 핵심 지목이 다르거나 비면 틀린 것이다.
"모르겠다" 는 언제나 틀린 것이다.

{items}

JSON 하나로만 답해라: {{"grades": [{{"i": 1, "ok": true, "why": "한 마디"}}]}}
"""


def chunks(xs: list, n: int) -> list[list]:
    return [xs[i:i + n] for i in range(0, len(xs), n)]


def collect(data: dict, key: str, group: list[Note],
            field: str | None) -> dict[int, object]:
    """묶음 안에서만 번호를 세고, 돌아온 번호를 카드 번호로 되돌린다.

    **모델이 준 번호를 그대로 믿으면 안 된다.** 46장을 20/20/6 으로 나눠 물었더니
    두 번째 묶음이 21~40 이 아니라 1~20 으로 답을 매겨 돌려줬고, 그게 첫 묶음의
    답을 통째로 덮었다. 그 결과 1~20 칸에는 21~40 의 답이 들어앉고 21~40 은 비었다.
    조용히 어긋났고 합계만 보면 멀쩡해 보였다.

    그래서 물을 때부터 묶음 안에서 1..N 으로만 세고, 그 자리로 되돌린다. 범위 밖
    번호는 버린다 — 어디로 갈지 알 수 없는 답을 아무 칸에나 넣지 않는다.

    `field` 가 None 이면 행을 통째로 돌려준다.
    """
    out: dict[int, object] = {}
    for row in data.get(key) or []:
        if not isinstance(row, dict):
            continue
        try:
            j = int(row["i"])
        except (KeyError, TypeError, ValueError):
            continue
        if 1 <= j <= len(group):
            out[group[j - 1].idx] = row if field is None else row.get(field)
    return out


def ask_text_only(notes: list[Note], **kw) -> dict[int, str]:
    out: dict[int, str] = {}
    for group in chunks(notes, BATCH_TEXT_ONLY):
        items = "\n".join(f"{j}. {n.q}" for j, n in enumerate(group, 1))
        data, _ = session.run_blind(ASK.format(items=items), label="B 질문만", **kw)
        out.update({k: str(v or "").strip()
                    for k, v in collect(data, "answers", group, "a").items()})
    return out


def ask_with_image(notes: list[Note], deck: Deck, **kw) -> dict[int, str]:
    out: dict[int, str] = {}
    for group in chunks(notes, BATCH_WITH_IMAGE):
        room = Path(tempfile.mkdtemp(prefix="doby-eyes-"))
        try:
            lines, present = [], []
            for n in group:
                src = deck.media_dir / n.images[0]
                if not src.exists():
                    continue
                present.append(n)
                name = f"q{len(present):03d}{Path(n.images[0]).suffix or '.png'}"
                shutil.copy(src, room / name)
                lines.append(f"{len(present)}. (사진: `{name}`) {n.q}")
            if not lines:
                continue
            data, _ = run_with_eyes(ASK_IMAGE.format(items="\n".join(lines)),
                                    room, label="A 사진 포함", **kw)
            out.update({k: str(v or "").strip()
                        for k, v in collect(data, "answers", present, "a").items()})
        finally:
            shutil.rmtree(room, ignore_errors=True)
    return out


def grade(notes: list[Note], answers: dict[int, str], label: str, **kw) -> dict[int, dict]:
    out: dict[int, dict] = {}
    pairs = [n for n in notes if n.idx in answers]
    for group in chunks(pairs, BATCH_TEXT_ONLY):
        items = "\n\n".join(
            f"{j}.\n  질문: {n.q}\n  원래 정답: {n.a}\n  답한 것: {answers[n.idx]}"
            for j, n in enumerate(group, 1))
        data, _ = session.run_blind(GRADE.format(items=items),
                                    label=f"채점 {label}", **kw)
        for idx, row in collect(data, "grades", group, None).items():
            out[idx] = {"ok": bool(row.get("ok")), "why": row.get("why", "")}
    return out


VERDICT = {(True, False): "image_required", (True, True): "image_decorative",
           (False, False): "unanswerable", (False, True): "inconsistent"}


def score(apkg: Path, out_dir: Path, **kw) -> dict:
    deck = load(apkg)
    notes = deck.image_notes
    if not notes:
        raise SystemExit(f"앞면에 그림이 있는 카드가 없다: {apkg.name}")

    t0 = time.time()
    print(f"  [{apkg.stem[:40]}] 이미지 카드 {len(notes)}장 / 전체 {len(deck.notes)}장")
    print("   A 사진 포함 …")
    a_ans = ask_with_image(notes, deck, **kw)
    print("   B 질문만 …")
    b_ans = ask_text_only(notes, **kw)
    # 답이 안 온 카드를 조용히 넘기지 않는다. 처음 돌렸을 때 46장 중 20장이
    # 소리 없이 비었고(묶음 하나가 통째로), 합계만 보면 멀쩡해 보였다.
    for label, got in (("A", a_ans), ("B", b_ans)):
        missing = [n.idx for n in notes if n.idx not in got]
        if missing:
            print(f"   ! {label} 응답 없음 {len(missing)}장: {missing[:12]}"
                  f"{' …' if len(missing) > 12 else ''}", file=sys.stderr)

    print("   채점 …")
    a_gr = grade(notes, a_ans, "A", **kw)
    b_gr = grade(notes, b_ans, "B", **kw)

    rows, tally = [], {}
    for n in notes:
        a_ok = a_gr.get(n.idx, {}).get("ok")
        b_ok = b_gr.get(n.idx, {}).get("ok")
        verdict = "ungraded" if a_ok is None or b_ok is None else VERDICT[(a_ok, b_ok)]
        tally[verdict] = tally.get(verdict, 0) + 1
        rows.append({"i": n.idx, "verdict": verdict, "q": n.q, "a": n.a,
                     "with_image": a_ans.get(n.idx), "text_only": b_ans.get(n.idx),
                     "a_ok": a_ok, "b_ok": b_ok})

    need = tally.get("image_required", 0)
    result = {
        "deck": apkg.name, "notes": len(deck.notes), "image_notes": len(notes),
        "tally": tally,
        "image_required_pct": round(100 * need / len(notes), 1),
        "wall_seconds": round(time.time() - t0, 1),
        "cards": rows,
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    dst = out_dir / f"score.{apkg.stem[:40].replace(' ', '_')}.json"
    dst.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    result["_path"] = str(dst)
    return result


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="이미지 카드에 사진이 필요한지 잰다")
    ap.add_argument("apkg", nargs="+")
    ap.add_argument("-o", "--out", default="out/score")
    ap.add_argument("--model")
    ap.add_argument("--timeout", type=int, default=1800)
    a = ap.parse_args(argv)

    kw = {"model": a.model, "timeout": a.timeout}
    results = [score(Path(p), Path(a.out), **kw) for p in a.apkg]

    print(f"\n{'덱':<44}{'이미지':>7}{'필요':>6}{'장식':>6}{'불가':>6}{'%':>7}")
    for r in results:
        t = r["tally"]
        print(f"{r['deck'][:43]:<44}{r['image_notes']:>7}"
              f"{t.get('image_required', 0):>6}{t.get('image_decorative', 0):>6}"
              f"{t.get('unanswerable', 0):>6}{r['image_required_pct']:>6.0f}%")
    return 0


if __name__ == "__main__":
    sys.exit(main())
