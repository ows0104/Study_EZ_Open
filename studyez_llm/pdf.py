"""Codex의 view_image에 전달할 PDF 쪽을 PNG로 만든다. 쪽 번호는 1부터 센다."""

from __future__ import annotations

import argparse
from pathlib import Path

import fitz


def page_numbers(spec: str, count: int) -> list[int]:
    result = []
    for span in spec.split(","):
        bounds = span.strip().split("-")
        lo, hi = int(bounds[0]), int(bounds[-1])
        if len(bounds) > 2 or not 1 <= lo <= hi <= count:
            raise ValueError(f"PDF 쪽 범위가 잘못됐다: {span} (전체 {count}쪽)")
        for page in range(lo, hi + 1):
            if page not in result:
                result.append(page)
    return result


def render(source: Path, pages: str, out: Path) -> list[Path]:
    with fitz.open(source) as doc:
        selected = page_numbers(pages, len(doc))
        out.mkdir(parents=True, exist_ok=True)
        paths = []
        for number in selected:
            page = doc[number - 1]
            scale = min(2.0, 1568 / max(page.rect.width, page.rect.height))
            path = out / f"page-{number:04d}.png"
            page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False).save(path)
            paths.append(path.resolve())
        return paths


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--pages", required=True)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    for path in render(args.source, args.pages, args.out):
        print(path)


if __name__ == "__main__":
    main()
