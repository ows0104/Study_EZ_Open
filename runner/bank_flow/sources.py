"""Select the attached PDF and cache lecture-specific exam source slices."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unicodedata
from pathlib import Path

from .. import deck
from . import REPO_ROOT

SLICE_CACHE = "jokbo.json"


def _cache_path(runs_dir: Path, run_id: str) -> Path:
    return runs_dir / run_id / "bank" / SLICE_CACHE


def jokbo_slices(runs_dir: Path, subject: str, sources: dict[str, Path]) -> dict[str, Path]:
    """run_id → 그 편의 족보 조각(.md). 조각이 없거나 문턱 아래인 편은 빠진다.

    판정은 하위 프로세스(`python -m quizgen.slicefor`)라 느리다 — 쓸기가 10분마다 도므로
    편마다 `runs/<id>/bank/jokbo.json` 에 적어 두고, **컷·필기·그 편의 족보 지정이 바뀔 때** 다시 잰다.
    """
    cut = deck.jokbo_dir(runs_dir, subject)
    if not (cut / "index.json").is_file():
        return {}
    revision = json.loads((cut / "index.json").read_text(encoding="utf-8")).get("professor_table_revision", "")
    pins_path = cut.parent / "pins.json"
    pins = json.loads(pins_path.read_text(encoding="utf-8")) if pins_path.is_file() else {}
    found: dict[str, Path] = {}
    pending: dict[str, Path] = {}
    for run_id, pdf in sources.items():
        pin_revision = json.dumps(pins[run_id], ensure_ascii=False, sort_keys=True) if run_id in pins else ""
        try:
            cached = json.loads(_cache_path(runs_dir, run_id).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            cached = None
        if (cached and cached.get("cut") == str(cut) and cached.get("source") == pdf.name
                and cached.get("professorRevision", "") == revision
                and cached.get("pinRevision", "") == pin_revision):
            if cached.get("slice") and Path(cached["slice"]).is_file():
                found[run_id] = Path(cached["slice"])
            continue
        pending[run_id] = pdf
    if not pending:
        return found
    with tempfile.TemporaryDirectory(prefix="slicefor-") as tmp:
        out = Path(tmp) / "out.json"
        proc = subprocess.run([sys.executable, "-m", "quizgen.slicefor", "--jokbo-dir", str(cut), "--out", str(out),
                               *map(str, pending.values())], cwd=REPO_ROOT, capture_output=True, text=True,
                              encoding="utf-8", errors="replace",
                              creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), stdin=subprocess.DEVNULL)
        if proc.returncode != 0 or not out.is_file():
            print(f"  ⚠ {subject}: 족보 조각을 못 쟀다 — {(proc.stderr or proc.stdout).strip()[-200:]}", flush=True)
            return found
        rows = json.loads(out.read_text(encoding="utf-8"))
    by_source = {Path(r["source"]).name: r for r in rows}
    for run_id, pdf in pending.items():
        row = by_source.get(pdf.name) or {}
        slice_md = str((REPO_ROOT / row["slice"]).resolve()) if row.get("slice") else ""
        path = _cache_path(runs_dir, run_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"cut": str(cut), "source": pdf.name, "slice": slice_md,
                                    "professorRevision": revision,
                                    "pinRevision": json.dumps(pins[run_id], ensure_ascii=False, sort_keys=True)
                                    if run_id in pins else "",
                                    "score": row.get("score"), "why": row.get("why", "")},
                                   ensure_ascii=False, indent=2), encoding="utf-8")
        if slice_md:
            found[run_id] = Path(slice_md)
    return found


def _notes_pdf(root: Path, subject: str, this_year: str, prev_year: str, runs_dir: Path, run_id: str) -> Path | None:
    # The publisher uses jokbo_slices; resolve its planner only when needed.
    from .. import publish

    plans, _ = publish.plan_subject(root, subject, this_year, prev_year, runs_dir)
    return next((p.item.path for p in plans if p.run_id == run_id), None)


def _attached_pdf(root: Path, subject: str, this_year: str, prev_year: str, runs_dir: Path,
                  run_id: str, sources: list[dict]) -> Path | None:
    """Keep the WEB-attached source version even if a newer local PDF arrives."""
    source = next((s for s in sources if s["kind"] == "notes_current"), None)
    if source:
        name = source["filename"]
        folder = root / subject / "필기" / this_year
        if Path(name).name == name:
            direct = folder / name
            if direct.is_file():
                return direct
            matches = [p for p in folder.rglob("*.pdf")
                       if unicodedata.normalize("NFC", p.name) == unicodedata.normalize("NFC", name)]
            if len(matches) == 1:
                return matches[0]
    return _notes_pdf(root, subject, this_year, prev_year, runs_dir, run_id)
