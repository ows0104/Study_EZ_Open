"""강의 PDF 여럿 → 각각의 족보 조각(.md). 러너가 Quiz Bank 재료로 올리려고 부른다.

    python -m quizgen.slicefor --jokbo-dir runs/_materials/약리학/261001-1426 --out out.json a.pdf b.pdf

판정은 덱을 만들 때와 **같은 것**이다(`assemble.slice_for_recorded` — 사람의 지정, 문턱 0.25,
실습 조각). 결과를 `--out` JSON 으로 쓴다 — 판정이 표준 출력에 사람이 읽을 말을 찍기 때문이다.

    [{"source": "...pdf", "slice": "...md" | null, "score": 0.91 | null, "why": "문턱 아래 …"}]
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import sys
from pathlib import Path

from .assemble import slice_for_recorded


def find(pdfs: list[Path], jokbo_dir: Path) -> list[dict]:
    out = []
    for pdf in pdfs:
        with contextlib.redirect_stdout(io.StringIO()):
            path, _, _, record = slice_for_recorded({"source": str(pdf)}, jokbo_dir)
        md = path.with_suffix(".md") if path else None
        out.append({"source": str(pdf),
                    "slice": str(md) if md and md.is_file() else None,
                    "score": record.get("score"),
                    "why": record.get("why_not") or ("" if md and md.is_file() else "조각의 .md 가 없다")})
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m quizgen.slicefor")
    ap.add_argument("--jokbo-dir", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("pdfs", nargs="+", type=Path)
    args = ap.parse_args(argv)
    args.out.write_text(json.dumps(find(args.pdfs, args.jokbo_dir), ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
