from runner.status_eta import estimate


def sample(seconds):
    return dict(subject='약리학', kind='bank', force=True, seconds=seconds)


def job(identifier, elapsed=0):
    return dict(id=identifier, subject='약리학', kind='bank', force=True, elapsedSeconds=elapsed)


def test_parallel_queue_counts_running_remaining_and_two_worker_slots():
    value = dict(running=[job(1, 300), job(2, 300)], waiting=[job(3), job(4)], maxRunning=2,
                 timingSamples=[sample(n) for n in (900, 1200, 1500, 1800)])
    result = estimate(value, 1000, 1000)
    assert result['running'][1]['range'] == (600, 1500)
    assert result['total'] == (1500, 3300)


def test_missing_or_exceeded_samples_do_not_claim_imminent_completion():
    value = dict(running=[job(1, 2000)], waiting=[],
                 timingSamples=[sample(n) for n in (900, 1200, 1500)])
    result = estimate(value, 1000, 1000)
    assert result['total'] is None
    assert result['running'][1]['overrun']
    value['timingSamples'] = []
    assert estimate(value, 1000, 1000)['total'] is None


def test_future_resume_is_counted_in_batch_time():
    from datetime import UTC, datetime
    waiting = job(1)
    waiting['resumeAt'] = datetime.fromtimestamp(2000, UTC).isoformat()
    value = dict(running=[], waiting=[waiting], maxRunning=2,
                 timingSamples=[sample(n) for n in (900, 1200, 1500)])
    assert estimate(value, 1000, 1000)['total'] == (1900, 2500)
