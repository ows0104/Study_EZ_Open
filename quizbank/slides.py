"""문항이 인용한 필기 PDF 쪽을 PNG 로 렌더한다 — 답을 볼 때 그 아래 붙는다.

한 문항이 여러 쪽을 인용할 수 있다(2026-10-03 관리자: 「참고슬라이드가 여러개일 수도 있어」).
쪽 번호는 프롬프트 §5 가 「PDF 파일의 실제 쪽 번호」로 적게 한다. 261002_02 에서 ChatGPT 가 적은
쪽 번호가 quizgen 의 slide_no 와 정확히 같았다(4·7·9·11·13–18·20–22).

파일 이름 `<run_id>_sNNN.png` 은 서버가 쪽 번호를 읽는 꼴이다(server/app/naming.py `_s(\\d{1,4})\\.png$`).
"""

from __future__ import annotations

from pathlib import Path

from server.app.bank_validation.pages import (
    MAX_RANGE as MAX_RANGE, cited_pages as cited_pages, pages_of as pages_of,
)

ZOOM = 1.6


def render(pdf: Path, pages: set[int] | list[int], out_dir: Path, run_id: str) -> tuple[list[Path], list[int]]:
    """`(그린 파일들, PDF 에 없는 쪽들)`."""
    import fitz  # PyMuPDF — 렌더할 때만 쓴다

    out_dir.mkdir(parents=True, exist_ok=True)
    made, missing = [], []
    with fitz.open(pdf) as doc:
        for no in sorted(set(pages)):
            if not 1 <= no <= doc.page_count:
                missing.append(no)
                continue
            path = out_dir / f"{run_id}_s{no:03d}.png"
            if not path.exists():
                doc[no - 1].get_pixmap(matrix=fitz.Matrix(ZOOM, ZOOM), alpha=False).save(path)
            made.append(path)
    return made, missing
