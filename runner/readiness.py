"""Read-only local notes and confirmed year matching; no generation or downloads."""
from __future__ import annotations

from pathlib import Path
import hashlib
import json
from . import ahead, filenames, matching


def packet_sources(root: Path, subject: str, prev_year: str, runs: Path) -> list[filenames.LectureFile]:
    """Explicit, provenance-checked derived inputs; never search arbitrary generated PDFs."""
    folder = runs / '_materials' / subject / 'prequiz-inputs'
    boundary = (root / subject / '필기' / prev_year).resolve()
    result = []
    for manifest in sorted(folder.glob('*.json')):
        value = json.loads(manifest.read_text(encoding='utf-8'))
        if value.get('subject') != subject or value.get('purpose') != 'approved-prequiz-input':
            raise ValueError('예습 합본 입력의 대상 확인 필요')
        pdf = Path(value['pdf']).resolve()
        if not pdf.is_relative_to(folder.resolve()) or pdf.is_symlink():
            raise ValueError('예습 합본 입력 경로 확인 필요')
        checks = [(pdf, value['sha256'])]
        if not value.get('sources'):
            raise ValueError('예습 합본 원본 기록 필요')
        for source in value['sources']:
            path = Path(source['path']).resolve()
            if not path.is_relative_to(boundary):
                raise ValueError('예습 합본 원본 범위 확인 필요')
            checks.append((path, source['sha256']))
        for path, expected in checks:
            with path.open('rb') as stream:
                if hashlib.file_digest(stream, 'sha256').hexdigest() != expected:
                    raise ValueError('예습 합본/원본이 변경되어 재확인 필요')
        item = filenames.parse(pdf)
        if item is None or item.key != value['input_id'] or str(item.year) != prev_year:
            raise ValueError('예습 합본 입력 ID 확인 필요')
        if ahead.load_pairs(runs, subject).get(value['run_id']) != item.key:
            raise ValueError('예습 합본의 명시적 매칭 필요')
        result.append(item)
    return result


def preview_sources(root: Path, subject: str, this_year: str, prev_year: str,
                    runs: Path, timetable: Path) -> dict[str, dict]:
    current = filenames.latest_versions(filenames.scan(root / subject / '필기' / this_year, this_year).files)
    previous = filenames.latest_versions(filenames.scan(root / subject / '필기' / prev_year, prev_year).files)
    extra = packet_sources(root, subject, prev_year, runs)
    if {f.key for f in previous} & {f.key for f in extra}:
        raise ValueError('파생 예습 입력 ID가 원본 강의와 겹칩니다.')
    previous += extra
    current_ids = filenames.assign_run_ids(current)
    pairs = ahead.load_pairs(runs, subject)
    result = {}
    from .preview_sources import History
    history = History(root, subject, this_year, prev_year, previous, runs, current_files=current)

    def row(target, previous, source, reason):
        selection = history.select(target, previous, source=source)
        if selection.item is None:
            return dict(ready=False, reason=reason, prevRunId='', prevPdf='', previewSource=selection.metadata)
        return dict(ready=True, reason='', prevRunId=selection.run_id,
                    prevPdf=str(selection.item.path), previewSource=selection.metadata)

    for match in matching.match_with_confirmed(current, previous, pairs):
        result[current_ids[match.this_year.uid]] = row(
            match.this_year, match.prev_year if match.confident else None, 'notes',
            '작년 필기 매칭 확인 필요' if match.prev_year else '연결할 작년 필기 없음')
    seats, _ = ahead.plan(subject, current, previous, timetable, runs, include_unmatched=True)
    for seat in seats:
        result[seat.cell.key] = row(seat.cell.as_lecture(seat.prev), seat.prev, 'timetable',
                                    seat.note or '작년 필기 매칭 확인 필요')
    return result
