import os
from pathlib import Path

from runner import status_phases as phases


def touch(folder: Path, relative: str, at: float):
    path = folder / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('{}', encoding='utf-8')
    os.utime(path, (at, at))


def test_stage_names_map_to_plain_phases():
    assert phases.phase_of('front/map/model-response.json') == 0
    assert phases.phase_of('generation/normalize.json') == 1
    assert phases.phase_of('generation/v4-coverage-1-0.json') == 1
    assert phases.phase_of('generation/v4-map-check-0.json') == 1
    assert phases.phase_of('generation/v4-add-0.json') == 2
    assert phases.phase_of('generation/v4-review-2-1.json') == 3
    assert phases.phase_of('generation/v4-coverage-fix-3-0.json') == 3
    assert phases.phase_of('generation/v4-fix-context-0.json') == 3
    assert phases.phase_of('generation/v4-context-0.json') == 4
    assert phases.phase_of('generation/medical-0.json') == 4
    assert phases.phase_of('generation/result.json') == 5
    assert phases.phase_of('published.json') == 5
    assert phases.phase_of('generation/evidence/x.json') is None
    assert phases.phase_of('generation/ledger.json') is None


def finished_run(folder, t0, minutes):
    """minutes: start offset of each phase, then the publish time."""
    names = ['front/map/input.json', 'generation/normalize.json', 'generation/v4-add-0.input.json',
             'generation/v4-review-0-0.input.json', 'generation/medical-0.input.json', 'generation/result.json']
    for name, offset in zip(names, minutes):
        touch(folder, name, t0 + offset * 60)
    touch(folder, 'published.json', t0 + minutes[-1] * 60)


def test_durations_are_medians_of_finished_phases_and_phase_only_moves_forward(tmp_path):
    finished_run(tmp_path / 'a', 10_000, [0, 15, 25, 35, 60, 63, 64])
    finished_run(tmp_path / 'b', 20_000, [0, 20, 30, 40, 70, 73, 74])
    typical = phases.durations(tmp_path)
    assert typical == {0: 17.5 * 60, 1: 600, 2: 600, 3: 27.5 * 60, 4: 180, 5: 60}

    run = tmp_path / 'now'
    start = 50_000
    touch(run, 'front/map/input.json', start)
    touch(run, 'generation/normalize.json', start + 18 * 60)
    touch(run, 'generation/v4-add-0.input.json', start + 28 * 60)
    touch(run, 'generation/v4-review-0-0.input.json', start + 38 * 60)
    # A later coverage pass inside review must not move the phase back.
    touch(run, 'generation/v4-coverage-2-0.input.json', start + 40 * 60)
    now = start + 48 * 60
    result = phases.progress(run, start, now, typical)
    assert result.phase == 3 and result.in_phase == 600
    assert result.remaining == 27.5 * 60 - 600 + 180 + 60
    assert not result.overrun
    late = phases.progress(run, start, start + 80 * 60, typical)
    assert late.overrun and late.remaining == 240
    assert phases.fraction(80 * 60, late.remaining, True) <= 0.97


def test_no_sample_means_no_number_and_resumed_files_are_ignored(tmp_path):
    run = tmp_path / 'r'
    touch(run, 'front/map/input.json', 1_000)          # an earlier attempt
    touch(run, 'generation/normalize.json', 90_000)
    result = phases.progress(run, 89_000, 90_600, {0: 60})
    assert result.phase == 1 and result.remaining is None
    assert phases.fraction(100, None, False) is None
