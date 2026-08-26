"""강의 PDF 를 슬라이드 한 장당 PNG 한 개로 편다.

**이 단계는 품질 장치가 아니라 통로다.** 실측 대상인 `260818_01` 의 clean.pdf 가
111MB 라 `Read` 가 열지 못한다(한도 100MB). GPT 웹에 파일을 올리면 그쪽이 알아서
페이지를 이미지로 펴서 모델에게 주는데, 그 자리를 여기가 대신한다.

그림을 골라 주지 않는다 — 페이지를 통째로 편다. 무엇이 그림인지, 어디를 자를지는
모델이 정한다. 그게 이 baseline 이 재려는 것이다.

사용:
    python -m doby_is_free.render <pdf> <out_dir> [--dpi 150]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import fitz


def render(pdf: Path, out_dir: Path, dpi: int = 150) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(pdf)
    zoom = dpi / 72.0
    mat = fitz.Matrix(zoom, zoom)
    written = []
    for page in doc:
        dst = out_dir / f"p{page.number + 1:03d}.png"
        page.get_pixmap(matrix=mat).save(dst)
        written.append(dst)
    doc.close()
    return written


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="PDF 를 페이지 PNG 로 편다")
    ap.add_argument("pdf")
    ap.add_argument("out_dir")
    ap.add_argument("--dpi", type=int, default=150)
    a = ap.parse_args(argv)

    files = render(Path(a.pdf), Path(a.out_dir), a.dpi)
    total = sum(f.stat().st_size for f in files)
    print(f"{len(files)}장 · {total / 1e6:.1f}MB → {a.out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
