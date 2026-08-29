"""이겨야 할 목표를 만든다 — 자료를 통째로 던지고 한 문장만 시킨다.

관리자의 물음이 출발점이다. *"내가 짠 코드와 그냥 GPT 웹에 파일을 올리고 '이걸로
이미지 안키를 만들어줘'라고 말한 것과 큰 차이가 없는 것 같다."* 그 말이 맞는지
재려면 **비교 대상이 이 저장소 안에서 재현 가능해야** 한다. GPT 웹 결과물 한 개는
표본이 아니다 — 다시 돌릴 수 없고, 같은 자로 잴 수도 없다.

그래서 여기서는 같은 일을 `claude -p` 로 한다. 조건은 GPT 웹 쪽에 맞춘다.

  - 프롬프트는 `prompts/naive.md` 한 장. 카드를 어떻게 만들라는 지시가 없다.
  - 학습계획도, 족보도, 검증도, 수선도, 재현검사도 없다. 한 번에 끝낸다.
  - 자료는 페이지 PNG 로만 준다. 어느 것이 그림인지 골라 주지 않는다.

**이건 우리가 개선할 물건이 아니다.** 여기에 규칙을 보태고 싶어지면 그건
`pdf2anki` 쪽에 보탤 것이지 여기가 아니다. 이 폴더의 값이 올라가면 기준선이
사라진다.

입력은 `pdf2anki` 와 같은 `run.config.json` 을 그대로 받는다. 출력은
`doby_is_free.pack` 이 `.apkg` 로 굽고, `doby_is_free.score` 가 우리 덱과 같은
자로 잰다.

사용:
    python -m doby_is_free.run runs/260818_01
    python -m doby_is_free.run runs/260818_01 --out out/doby/260818_01
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from pdf2anki import session

from . import render

PROMPTS = Path(__file__).parent / "prompts"
DEFAULT_PROMPT = PROMPTS / "naive.md"

# 페이지를 몇 장씩 한 세션에 줄 것인가. 119장을 한 세션에 넣으면 이미지 토큰만
# 190k 라 컨텍스트가 넘친다. 0 이면 자르지 않는다.
#
# 자르는 것 자체는 우리 파이프라인도 한다(260818_01 은 context.1of4 … 4of4 였다).
# 다만 **자른 자리가 baseline 에 불리하게 작동할 수 있다** — 묶음 사이의 중복을
# 모델이 못 본다. 유리하게 작동하는 자리는 없다. 그러니 여기서 나온 값은
# baseline 의 하한이지 상한이 아니다.
DEFAULT_BATCH = 30


def load_config(prep_dir: Path) -> dict:
    cfg = json.loads((prep_dir / "run.config.json").read_text(encoding="utf-8"))
    for key in ("pdf", "deck", "id"):
        if not cfg.get(key):
            raise SystemExit(f"run.config.json 에 {key} 가 없다: {prep_dir}")
    return cfg


def pick_pdf(cfg: dict, prep_dir: Path) -> Path:
    """원본 PDF. 없으면 prep 이 만들어 둔 clean.pdf 로 물러선다.

    clean.pdf 는 필기 주석이 걷힌 판이다. **원본이 우선인 이유**는 GPT 웹에 올린
    것이 원본이었기 때문이다 — 조건을 맞춘다.
    """
    src = Path(cfg["pdf"])
    if src.exists():
        return src
    fallback = prep_dir / "clean.pdf"
    if fallback.exists():
        print(f"  원본을 못 찾아 clean.pdf 로 간다 ({src.name})", file=sys.stderr)
        return fallback
    raise SystemExit(f"PDF 를 못 찾았다: {src}")


def batches(pages: list[Path], size: int) -> list[list[Path]]:
    if size <= 0:
        return [pages]
    return [pages[i:i + size] for i in range(0, len(pages), size)]


def resolve_prompt(name: str | None) -> Path:
    """프롬프트 파일. 이름만 주면 `prompts/` 에서 찾는다."""
    if not name:
        return DEFAULT_PROMPT
    cand = Path(name)
    if cand.exists():
        return cand
    for guess in (PROMPTS / name, PROMPTS / f"{name}.md"):
        if guess.exists():
            return guess
    raise SystemExit(f"프롬프트를 못 찾았다: {name}")


def prompt_for(prompt: Path, group: list[Path], all_pages: list[Path],
               out_name: str) -> str:
    body = prompt.read_text(encoding="utf-8")
    body = body.replace("p{N}.png", f"p{len(all_pages):03d}.png")
    body = body.replace("cards.json", out_name)
    if len(group) < len(all_pages):
        first, last = group[0].stem, group[-1].stem
        body += (f"\n\n이번에 볼 자료는 `pages/{first}.png` 부터 `pages/{last}.png` 까지다."
                 f" (전체 {len(all_pages)}장 중 일부)\n")
    return body


def run(prep_dir: Path, out_dir: Path, *, dpi: int, batch: int,
        model: str | None, timeout: int, prompt: Path = DEFAULT_PROMPT) -> dict:
    cfg = load_config(prep_dir)
    pdf = pick_pdf(cfg, prep_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    t0 = time.time()
    pages_dir = out_dir / "pages"
    if pages_dir.exists() and any(pages_dir.glob("p*.png")):
        pages = sorted(pages_dir.glob("p*.png"))
        print(f"  페이지 {len(pages)}장 (이미 있음)")
    else:
        print(f"  펴는 중 … {pdf.name}")
        pages = render.render(pdf, pages_dir, dpi)
        print(f"  페이지 {len(pages)}장")

    groups = batches(pages, batch)
    cards, runs = [], []
    for i, group in enumerate(groups, 1):
        name = f"cards.{i}of{len(groups)}.json" if len(groups) > 1 else "cards.json"
        dst = out_dir / name
        if dst.exists():
            print(f"  [{i}/{len(groups)}] 건너뜀 (이미 있음)")
        else:
            print(f"  [{i}/{len(groups)}] 세션 … {group[0].stem}-{group[-1].stem}")
            info = session.run_agent(
                prompt_for(prompt, group, pages, name),
                cwd=out_dir, model=model, timeout=timeout,
                label=f"doby {i}/{len(groups)}")
            runs.append({"batch": i, "cost_usd": info.get("cost_usd"),
                         "turns": info.get("turns"), "usage": info.get("usage"),
                         "duration_ms": info.get("duration_ms")})
            if not dst.exists():
                raise SystemExit(f"세션이 {name} 를 쓰지 않았다. 응답:\n"
                                 f"{str(info.get('text'))[:600]}")
        chunk = json.loads(dst.read_text(encoding="utf-8"))
        cards.extend(chunk.get("cards", []))

    merged = out_dir / "cards.merged.json"
    merged.write_text(json.dumps({"cards": cards}, ensure_ascii=False, indent=1),
                      encoding="utf-8")

    meta = {
        "source": str(pdf), "prep_dir": str(prep_dir),
        "prompt": prompt.name,
        "deck": cfg["deck"], "id": cfg["id"],
        "pages": len(pages), "dpi": dpi, "batch": batch,
        "sessions": len(runs), "cards": len(cards),
        "with_image": sum(1 for c in cards if c.get("page")),
        "wall_seconds": round(time.time() - t0, 1),
        "cost_usd": round(sum(r["cost_usd"] or 0 for r in runs), 4) or None,
        "runs": runs,
    }
    (out_dir / "run.meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    return meta


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="한 문장만 주고 덱을 만들게 한다 (기준선)")
    ap.add_argument("prep_dir", help="pdf2anki 의 런 폴더 (run.config.json 이 있는 곳)")
    ap.add_argument("--out", help="결과 폴더. 기본은 <prep_dir>/doby")
    ap.add_argument("--prompt", help="프롬프트 파일 또는 prompts/ 안의 이름. "
                                     "기본은 naive.md (기준선)")
    ap.add_argument("--dpi", type=int, default=150)
    ap.add_argument("--batch", type=int, default=DEFAULT_BATCH,
                    help="한 세션에 줄 페이지 수. 0 이면 자르지 않는다")
    ap.add_argument("--model")
    ap.add_argument("--timeout", type=int, default=3600)
    a = ap.parse_args(argv)

    prep_dir = Path(a.prep_dir)
    out_dir = Path(a.out) if a.out else prep_dir / "doby"
    meta = run(prep_dir, out_dir, dpi=a.dpi, batch=a.batch,
               model=a.model, timeout=a.timeout,
               prompt=resolve_prompt(a.prompt))
    print(f"\n카드 {meta['cards']}장 (사진 {meta['with_image']}장) · "
          f"{meta['wall_seconds']:.0f}초 · 세션 {meta['sessions']} · "
          f"${meta['cost_usd'] or 0:.2f}")
    print(f"→ {out_dir / 'cards.merged.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
