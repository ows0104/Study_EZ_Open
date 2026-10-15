"""Prepare and cache source-only exam points while WEB authors questions."""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from .question_first import cached_points, extract_points
from .session import SessionError
from .runtime import record as record_runtime


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--context", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--cache-root", type=Path, required=True)
    parser.add_argument("--jokbo", type=Path)
    parser.add_argument("--model")
    parser.add_argument("--min-source-age", type=int, default=0)
    args = parser.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True)
    record_runtime(args.out, 'started')
    try:
        context = json.loads(args.context.read_text(encoding="utf-8"))
        sources = context["sources"]
        pdf_source = next(s["id"] for s in sources if s["kind"] == "notes_current")
        reuse = cached_points(args.cache_root, args.pdf, context["title"], sources,
                              pdf_source=pdf_source, jokbo=args.jokbo)
        if reuse is None:
            left = args.min_source_age - (time.time() - args.pdf.stat().st_mtime)
            if left > 0:
                print("── 동기화 대기", flush=True)
            while left > 0:
                time.sleep(min(30, left))
                left = args.min_source_age - (time.time() - args.pdf.stat().st_mtime)
        print("── 저장된 원본 독립 포인트 재사용" if reuse else "── 원본 독립 출제포인트 추출", flush=True)
        points, usage = extract_points(args.pdf, context["title"], sources, args.out,
                                      pdf_source=pdf_source, jokbo=args.jokbo, reuse=reuse, model=args.model)
        result = {"completed": True, "reused": reuse is not None, "points": len(points),
                  "pointPlanPath": str((args.out / "authored-points.json").resolve()), "usage": usage}
        (args.out / "points-result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        record_runtime(args.out, 'finished')
        return 0
    except (SessionError, OSError, ValueError, KeyError, StopIteration, TypeError) as cause:
        record_runtime(args.out, 'failed')
        print(f"멈췄다 — 원본 독립 포인트: {cause}", flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
