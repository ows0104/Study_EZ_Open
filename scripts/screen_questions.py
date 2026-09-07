"""사진만 보고 풀 수 있는 문항인지 Claude에게 물어 본다.

    uv run --python 3.13 --with anthropic python scripts/screen_questions.py \
        --qtype "충란 동정" "종 동정" --limit 50

출력: data/screen_results.jsonl   (한 줄에 한 문항, 다시 돌리면 이어서 한다)
      data/screen_flagged.csv     사람이 볼 것만 추린 표

## 무엇을 재는가

"이 문항이 틀렸다"가 아니라 **"사진에 답이 들어 있는가"**를 본다. 물어보는 것은 셋이다.

  - 어느 보기를 고르겠는가
  - 사진만으로 정할 수 있었는가, 아니면 지식으로 메웠는가
  - **사진이 똑같이 받쳐 주는 다른 보기가 있는가** ← 이게 핵심이다

셋째가 정답을 포함하면 그 문항은 사진으로 안 갈린다. 유무구조충 충란처럼
실제로 구별이 불가능한 짝이 보기에 같이 들어간 경우가 이렇게 잡힌다.

## 이 결과를 어떻게 읽어야 하나

**모델이 틀린 것과 문항이 깨진 것은 다르다.** 모델은 기생충학 실습 사진에
사람만큼 익숙하지 않아서, 사람이 푸는 문항도 틀린다. 그래서 이건 판정이 아니라
**추려 주는 장치**다. 걸린 것만 사람이 사진을 열어 보면 된다.

거꾸로는 조금 더 믿을 만하다 — 모델이 사진만으로 자신 있게 맞혔다면
적어도 사진에 근거가 있다는 뜻이다.

## 값

문항 하나에 사진 한 장(900px)이라 1.5k 토큰 남짓이다. 555문항이면 대략 몇 달러.
`--limit`으로 잘라 돌려 보고 늘리는 편이 낫다.
"""

import argparse
import base64
import csv
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor

from pydantic import BaseModel

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
BUILD = os.path.join(ROOT, "build")
MODEL = "claude-opus-5"

SYSTEM = """당신은 의과대학 기생충학 실습 시험(땡시)의 문항을 검수한다.

주어진 사진 한 장과 4개의 보기를 보고 다음을 판정하라.

  - choice: 사진을 근거로 고를 보기의 번호 (0부터)
  - from_image: 사진에 있는 것만으로 정했으면 true. 사진으로는 못 정하고
    문제 유형이나 사전 지식으로 메웠으면 false.
  - equally_supported: **사진이 똑같이 받쳐 주는 보기의 번호를 전부** 적는다.
    choice도 포함한다. 사진으로 갈리는 보기가 하나뿐이면 원소가 하나다.
    예: 유구조충과 무구조충의 충란은 광학현미경으로 구별되지 않으므로
    둘 다 보기에 있으면 둘 다 적는다.
  - reason: 한 문장. 사진의 어떤 소견을 근거로 삼았는지.

사진이 흐리거나 잘려서 판단이 안 되면 from_image를 false로 두고 reason에 적어라.
모르는 것을 아는 척하지 마라 — 이 검수의 목적은 정답을 맞히는 것이 아니라
**사진에 답이 들어 있는지** 가리는 것이다."""


class Verdict(BaseModel):
    choice: int
    from_image: bool
    equally_supported: list[int]
    reason: str


def load_done(path):
    done = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    r = json.loads(line)
                    done[r["id"]] = r
    return done


def ask(client, q, img_dir):
    img_path = os.path.join(img_dir, q["image"])
    with open(img_path, "rb") as fh:
        b64 = base64.standard_b64encode(fh.read()).decode("utf-8")
    opts = "\n".join(f"{i}. {o}" for i, o in enumerate(q["options"]))
    prompt = f"[유형] {q['qtype']}\n[문제] {q['stem']}\n[보기]\n{opts}"
    resp = client.messages.parse(
        model=MODEL,
        max_tokens=4000,
        system=SYSTEM,
        messages=[{"role": "user", "content": [
            {"type": "image", "source": {"type": "base64",
                                         "media_type": "image/jpeg", "data": b64}},
            {"type": "text", "text": prompt},
        ]}],
        output_format=Verdict,
    )
    # 안전 분류기가 요청을 거절하면 content가 비어 있다. 읽기 전에 본다.
    if resp.stop_reason == "refusal":
        return {"refused": True}
    v = resp.parsed_output
    return {
        "choice": v.choice,
        "from_image": v.from_image,
        "equally_supported": sorted(set(v.equally_supported)),
        "reason": v.reason,
        "in_tokens": resp.usage.input_tokens,
        "out_tokens": resp.usage.output_tokens,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--qtype", nargs="*", default=["충란 동정", "종 동정"],
                    help="검수할 문항 유형. 비우면 전부")
    ap.add_argument("--limit", type=int, default=0, help="앞에서 몇 개만")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--out", default=os.path.join(DATA, "screen_results.jsonl"))
    args = ap.parse_args()

    import anthropic

    db = json.load(open(os.path.join(BUILD, "quiz_db.json"), encoding="utf-8"))
    qs = db["questions"]
    if args.qtype:
        qs = [q for q in qs if q["qtype"] in args.qtype]
    done = load_done(args.out)
    todo = [q for q in qs if q["id"] not in done]
    if args.limit:
        todo = todo[: args.limit]
    print(f"대상 {len(qs)}문항 · 이미 본 것 {len(done)} · 이번에 {len(todo)}")
    if not todo:
        print("새로 볼 것이 없습니다.")

    client = anthropic.Anthropic()
    img_dir = os.path.join(BUILD, "images")
    lock_out = open(args.out, "a", encoding="utf-8")

    def one(q):
        try:
            r = ask(client, q, img_dir)
        except Exception as e:                      # 한 문항이 죽어도 나머지는 돈다
            r = {"error": f"{type(e).__name__}: {e}"}
        r["id"] = q["id"]
        r["answer"] = q["answer"]
        r["qtype"] = q["qtype"]
        r["image"] = q["image"]
        r["options"] = q["options"]
        r["stem"] = q["stem"]
        return r

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for n, r in enumerate(pool.map(one, todo), 1):
            lock_out.write(json.dumps(r, ensure_ascii=False) + "\n")
            lock_out.flush()
            done[r["id"]] = r
            if n % 10 == 0:
                print(f"  {n}/{len(todo)}")
    lock_out.close()

    # ── 추리기
    rows, cost_in, cost_out = [], 0, 0
    wrong = ambiguous = unusable = errs = 0
    for r in done.values():
        if r.get("error") or r.get("refused"):
            errs += 1
            continue
        cost_in += r.get("in_tokens", 0)
        cost_out += r.get("out_tokens", 0)
        eq = r.get("equally_supported") or []
        why = []
        if r["choice"] != r["answer"]:
            why.append("모델이 다른 답을 고름")
            wrong += 1
        if len(eq) > 1 and r["answer"] in eq:
            why.append("사진이 정답 말고 다른 보기도 똑같이 받침")
            ambiguous += 1
        if not r.get("from_image"):
            why.append("사진만으로는 못 정함")
            unusable += 1
        if why:
            rows.append((r, " / ".join(why), eq))

    out_csv = os.path.join(DATA, "screen_flagged.csv")
    with open(out_csv, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["id", "유형", "사진", "지문", "정답", "모델의 답",
                    "사진이 똑같이 받치는 보기", "걸린 이유", "모델의 근거"])
        for r, why, eq in sorted(rows, key=lambda x: x[0]["qtype"]):
            o = r["options"]
            w.writerow([r["id"], r["qtype"], r["image"], r["stem"],
                        o[r["answer"]], o[r["choice"]] if 0 <= r["choice"] < len(o) else "?",
                        " | ".join(o[i] for i in eq if 0 <= i < len(o)),
                        why, r.get("reason", "")])

    seen = len(done) - errs
    print(f"\n본 문항 {seen}개 (오류 {errs})")
    print(f"  모델이 다른 답을 고름            {wrong}")
    print(f"  사진이 정답 외의 보기도 받침     {ambiguous}   ← 여기가 핵심")
    print(f"  사진만으로는 못 정했다고 함      {unusable}")
    print(f"  추린 것 {len(rows)}개 → {os.path.relpath(out_csv, ROOT)}")
    # 값은 Opus 5 기준 입력 $5 / 출력 $25 per MTok
    print(f"\n토큰 입력 {cost_in:,} · 출력 {cost_out:,} "
          f"(대략 ${cost_in / 1e6 * 5 + cost_out / 1e6 * 25:.2f})")
    print("\n모델이 틀린 것과 문항이 깨진 것은 다르다. 걸린 것만 사진을 열어 볼 것.")


if __name__ == "__main__":
    main()
