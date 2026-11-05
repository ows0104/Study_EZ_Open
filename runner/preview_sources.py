"""One read-only historical selector shared by publishing and preview readiness."""
from __future__ import annotations

from dataclasses import dataclass, replace
from functools import lru_cache
import hashlib
from pathlib import Path
import unicodedata

from studyez_contracts.preview_sources import fingerprint, professor_names, validate
from . import filenames, matching


@lru_cache(maxsize=512)
def _digest(path: str, size: int, modified: int):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


@dataclass
class Selection:
    item: filenames.LectureFile | None
    metadata: dict
    run_id: str = ''


class History:
    def __init__(self, root: Path, subject: str, year: str, baseline_year: str,
                 previous: list[filenames.LectureFile], runs: Path, *, current_files=()):
        self.year, self.baseline_year = int(year), int(baseline_year)
        self.runs = runs
        groups = {}
        for item in current_files:
            groups.setdefault((item.key, item.stem, item.seq), []).append(item)
        self.conflicts = {item.uid for items in groups.values()
                          if len({tuple(professor_names(f.professors)) for f in items}) > 1
                          for item in items}
        self.files = {}
        self.unparsed = {}
        self.coverage = dict(available=[], missing=[], incomplete=[], failed=[])
        for y in range(self.year - 1, self.year - 6, -1):
            folder = root / subject / '필기' / str(y)
            try:
                if not folder.is_dir():
                    self.coverage['missing'].append(y)
                    self.files[y] = []
                    continue
                scan = filenames.scan(folder, str(y))
                self.files[y] = filenames.latest_versions(scan.files)
                self.unparsed[y] = scan.unparsed + [f.path for f in scan.misfiled]
                self.coverage['available'].append(y)
                if self.unparsed[y]:
                    self.coverage['incomplete'].append(y)
            except OSError:
                self.coverage['failed'].append(y)
                self.files[y] = []
        # Derived packets remain explicit, provenance-checked baseline inputs.
        self.ids = filenames.assign_run_ids(previous + [f for y, fs in self.files.items()
                                                       if y != self.baseline_year for f in fs])

    def select(self, target, baseline=None, *, source='notes', reason=''):
        teachers = professor_names(target.professors)
        old_teachers = professor_names(baseline.professors) if baseline else []
        anchor = replace(target, stem=baseline.stem, seq=baseline.seq) if baseline else target
        selected = None
        known_correspondence = bool(baseline and old_teachers)
        conflict = source == 'notes' and target.uid in self.conflicts
        uncertain = not teachers or conflict
        partial = False
        # Packets can cover multiple topics; a filename match cannot authorize a new scope.
        packet = baseline is not None and baseline.path.resolve().is_relative_to(self.runs.resolve())
        if conflict:
            reason = '올해 필기 간 담당 표기 충돌 · 작년 자료 사용'
        elif packet:
            uncertain = True
            reason = '확인된 합본 사용 · 예전 동일 교수 필기로 변경하려면 범위 확인 필요'
        elif teachers:
            for year, files in self.files.items():
                pool = [f for f in files if professor_names(f.professors) == teachers]
                match = matching.match_years([anchor], pool)[0]
                # A confirmed baseline remains authoritative even for renamed topics.
                if year == self.baseline_year and baseline and old_teachers == teachers:
                    selected = baseline
                    break
                if match.prev_year is not None:
                    ranked = sorted((matching.score(anchor, f) for f in pool), reverse=True)
                    # Equal top candidates are not resolved by filename order.
                    if match.confident and (len(ranked) < 2 or ranked[0] - ranked[1] >= matching.CONFIDENT_MARGIN):
                        selected = match.prev_year
                        break
                    uncertain = True
                for f in files:
                    if matching.score(anchor, f) >= matching.CONFIDENT_SCORE:
                        names = professor_names(f.professors)
                        if not names:
                            uncertain = True
                        else:
                            known_correspondence = True
                            if names != teachers and set(teachers) & set(names):
                                partial = True
                # Only relevant unreadable filenames undermine this lecture's absence result.
                for path in self.unparsed.get(year, []):
                    stem = filenames.canonical(path.stem)
                    if anchor.stem in stem or any(name in stem for name in teachers):
                        uncertain = True
            if self.coverage['failed']:
                uncertain = True
        same = selected is not None
        if not same and not known_correspondence:
            uncertain = True
        if selected is None:
            selected = baseline
        if not reason:
            if same:
                reason = '동일 교수의 최신 보유 필기'
            elif uncertain:
                reason = '교수/과거 자료 확인 필요 · 확인된 작년 자료 사용' if baseline else '교수/과거 자료 확인 필요'
            elif partial:
                reason = '과거 담당 일부 일치 · 작년 자료 사용'
            else:
                reason = '보유 최근 5년 동일 교수 필기 없음 · 작년 자료 사용' if baseline else '보유 최근 5년 동일 교수 필기 없음 · 작년 대응 확인 필요'
        selected_value = None
        if selected:
            stat = selected.path.stat()
            selected_teachers = professor_names(selected.professors)
            relation = ('unknown' if not teachers or not selected_teachers else
                        'same' if selected_teachers == teachers else
                        'partial' if set(teachers) & set(selected_teachers) else 'different')
            selected_value = dict(year=selected.year, filename=unicodedata.normalize('NFC', selected.path.name),
                                  professors=selected_teachers, sizeBytes=stat.st_size,
                                  sha256=_digest(str(selected.path.resolve()), stat.st_size, stat.st_mtime_ns),
                                  match=relation)
        value = dict(version=1, year=self.year, currentProfessors=teachers, currentSource=source,
                     date=target.date, startTime=target.start_time, baselineYear=self.baseline_year,
                     baselineProfessors=old_teachers,
                     baselineFilename=unicodedata.normalize('NFC', baseline.path.name) if baseline else '',
                     changed=(teachers != old_teachers) if teachers and old_teachers and not conflict else None,
                     newProfessor=False if same or partial else None if uncertain else True,
                     status='needs_review' if uncertain or partial or selected is None else 'ok',
                     reason=reason, coverage=self.coverage, selected=selected_value)
        value['fingerprint'] = fingerprint(value)
        return Selection(selected, validate(value), self.ids.get(selected.uid, selected.key) if selected else '')
