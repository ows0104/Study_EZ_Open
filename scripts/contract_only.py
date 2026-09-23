"""덱은 이미 나와 있고 계약만 안 붙은 편에 계약을 붙인다.

**`runner rebuild` 로는 안 되는 자리가 있었다.** 그쪽은 계약 전에 덱을 다시 굽는데
`runner.deck.rebuild` 에 `--allow-defects` 가 없어서 재현 결함이 하나라도 있는 편은
`quizgen.build` 가 거부했다. **2026-09-23 에 붙였다** — 문지기가 결함으로 막지 않게
되고, 사이트에서 고친 카드를 바로 그 편들에 다시 구워 얹어야 해서다. 이제는 덱을
다시 굽기 싫을 때(모델 산출물 그대로 계약만 새로 쓰고 싶을 때) 쓰는 자리다.

파이프라인(`quizgen.run`)은 이미 `--allow-defects` 로 그 덱을 구워 뒀다. 여기서는
굽지 않고 계약만 부른다.

    python scripts/contract_only.py 260902_01 [...]
"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from runner import deck, filenames  # noqa: E402

RUNS = REPO_ROOT / "runs"

failed = 0
for run_id in sys.argv[1:]:
    run_dir = RUNS / run_id
    apkg = deck.apkg_of(run_dir, deck.MAIN)
    if apkg is None:
        print(f"  ✗ {run_id} — 덱이 없다. 먼저 만들어라")
        failed += 1
        continue
    parsed = filenames.parse(deck.source_pdf(run_dir))
    title = parsed.title if parsed else run_dir.name
    meta = deck.contract(run_dir, run_id, title, deck.MAIN)
    defects = meta.get("reproduce_defects") or []
    print(f"  ✓ {run_id} — {meta['item_count']}장 · 미디어 {meta['verified']['media']}개"
          + (f" · 결함 {len(defects)}건 → 올라가면 「카드 검토」에 뜬다" if defects else ""))
sys.exit(1 if failed else 0)
