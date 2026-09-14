"""덱은 이미 나와 있고 계약만 안 붙은 편에 계약을 붙인다.

**`studyez rebuild` 로는 안 되는 자리가 있다.** 그쪽은 계약 전에 덱을 다시 굽는데
`studyez.deck.rebuild` 에는 `--allow-defects` 가 없다(`pdf2anki/run.py` 에만 있다).
그래서 재현 결함이 하나라도 있는 편은 `pdf2anki.build` 가 거부하고, 계약이 안 붙고,
`run.meta.json` 이 옛 실행 것으로 남는다 — **문지기가 잡아야 해서 메타가 제일
필요한 편이 정확히 그 편이다.**

파이프라인(`pdf2anki.run`)은 이미 `--allow-defects` 로 그 덱을 구워 뒀다. 여기서는
굽지 않고 계약만 부른다.

    python scripts/contract_only.py 260902_01 [...]
"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from studyez import deck, filenames  # noqa: E402
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
          + (f" · 결함 {len(defects)}건 → 문지기가 잡는다" if defects else ""))
sys.exit(1 if failed else 0)
