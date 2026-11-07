"""Oversized original crops: deterministic scale step-down and the no-replay render recovery contract."""
import copy
import random

import fitz
import pytest

from quizbank import connection_visuals as visual
from studyez_contracts.roots import generation_v2 as c, document_hash, media


def noisy_pdf(path):
    random.seed(7)
    doc = fitz.open()
    page = doc.new_page(width=400, height=300)
    pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 400, 300), False)
    pix.set_rect(pix.irect, (255, 255, 255))
    for y in range(300):
        for x in range(0, 400, 2):
            pix.set_pixel(x, y, (random.randrange(256), random.randrange(256), random.randrange(256)))
    page.insert_image(page.rect, pixmap=pix)
    doc.save(path)


SPEC = {'question_id': 'Q1', 'source_id': 'S1', 'page': 1, 'crop': [0, 0, 1, 1], 'reason': 'whole page'}


def test_crops_that_fit_keep_the_original_2x_bytes(tmp_path):
    noisy_pdf(tmp_path / 'a.pdf')
    first = visual.page_crop(tmp_path / 'a.pdf', SPEC)
    fixed = visual.page_crop(tmp_path / 'a.pdf', SPEC, scales=(2,))
    assert first == fixed and first[1] == 800


def test_oversized_crop_steps_down_until_it_fits(tmp_path, monkeypatch):
    noisy_pdf(tmp_path / 'a.pdf')
    full, _w, _h = visual.page_crop(tmp_path / 'a.pdf', SPEC, scales=(2,))
    monkeypatch.setattr(media, 'MAX_IMAGE', len(full) - 1)
    body, width, height = visual.page_crop(tmp_path / 'a.pdf', SPEC)
    assert len(body) <= len(full) - 1 and width < 800 and (width, height) != (800, 600)
    assert visual.page_crop(tmp_path / 'a.pdf', SPEC) == (body, width, height)  # deterministic


def _proof_case():
    stages = {'normalize': {'status': 'completed', 'inputHash': 'a' * 64, 'outputHash': 'b' * 64, 'rawOutputHash': 'c' * 64},
              'generate': {'status': 'failed', 'inputHash': 'd' * 64, 'rawOutputHash': 'e' * 64, 'usageHash': 'f' * 64}}
    old = {'identity': '1' * 64, 'pipelineVersion': c.POLICY, 'repairRounds': 1, 'stages': stages}
    proof = {'priorLedger': old, 'priorLedgerHash': document_hash(old), 'packetHash': '2' * 64, 'currentRuntimeHash': '3' * 64,
             'reason': 'oversized original crop', 'stage': 'generate',
             'oversized': [{'question_id': 'Q1', 'page': 13, 'bytes': media.MAX_IMAGE + 1}], 'toolSha256': '4' * 64, 'modelReplay': False}
    now = copy.deepcopy(stages)
    now['generate'].update(status='completed', outputHash='5' * 64, briefHash='6' * 64)
    meta = {'renderRecoveries': [{'proof': proof, 'proofHash': document_hash(proof)}], 'inputHash': '2' * 64,
            'runtimeHash': '3' * 64, 'repairRounds': 1}
    return meta, {k: {'name': k, **v} for k, v in now.items()}


def test_render_recovery_contract_accepts_one_unchanged_call():
    meta, stages = _proof_case()
    assert c.validate_render_recoveries(meta, stages) == meta['renderRecoveries']
    assert c.validate_render_recoveries({'inputHash': 'x'}, stages) == []


@pytest.mark.parametrize('change', [
    lambda m, s: m['renderRecoveries'][0]['proof'].update(modelReplay=True),
    lambda m, s: m['renderRecoveries'][0]['proof'].update(oversized=[]),
    lambda m, s: m['renderRecoveries'][0]['proof']['oversized'][0].update(bytes=10),
    lambda m, s: s['generate'].update(rawOutputHash='9' * 64),
    lambda m, s: s['normalize'].update(outputHash='9' * 64),
    lambda m, s: m.update(repairRounds=0),
    lambda m, s: m.update(runtimeHash='7' * 64),
])
def test_render_recovery_contract_rejects_changes(change):
    meta, stages = _proof_case()
    change(meta, stages)
    row = meta['renderRecoveries'][0]
    row['proofHash'] = document_hash(row['proof'])
    with pytest.raises(ValueError):
        c.validate_render_recoveries(meta, stages)


def _medical_case():
    stages = {'normalize': {'status': 'completed', 'inputHash': 'a' * 64, 'outputHash': 'b' * 64, 'rawOutputHash': 'c' * 64},
              'medical-2': {'status': 'failed', 'inputHash': 'd' * 64, 'rawOutputHash': 'e' * 64, 'usageHash': 'f' * 64}}
    old = {'identity': '1' * 64, 'pipelineVersion': c.POLICY, 'repairRounds': 3, 'stages': stages}
    proof = {'priorLedger': old, 'priorLedgerHash': document_hash(old), 'packetHash': '2' * 64, 'currentRuntimeHash': '3' * 64,
             'reason': 'review omitted ok verdicts', 'stage': 'medical-2', 'rejectedRawHash': 'e' * 64,
             'reviewed': ['Q1'], 'missing': ['Q2'], 'toolSha256': '4' * 64, 'modelReplay': True}
    now = {'normalize': dict(stages['normalize']),
           'medical-2': {'status': 'completed', 'inputHash': 'd' * 64, 'rawOutputHash': '8' * 64, 'outputHash': '9' * 64, 'usageHash': '7' * 64}}
    meta = {'medicalRetries': [{'proof': proof, 'proofHash': document_hash(proof)}], 'inputHash': '2' * 64,
            'runtimeHash': '3' * 64, 'repairRounds': 3}
    return meta, {k: {'name': k, **v} for k, v in now.items()}


def test_medical_retry_contract_accepts_one_fresh_review_of_the_same_input():
    meta, stages = _medical_case()
    assert c.validate_medical_retries(meta, stages) == meta['medicalRetries']
    pending = {k: v for k, v in stages.items() if k != 'medical-2'}
    assert c.validate_medical_retries(meta, pending, pending=True)
    with pytest.raises(ValueError):
        c.validate_medical_retries(meta, pending)


@pytest.mark.parametrize('change', [
    lambda m, s: m['medicalRetries'][0]['proof'].update(modelReplay=False),
    lambda m, s: m['medicalRetries'][0]['proof'].update(missing=[]),
    lambda m, s: s['medical-2'].update(inputHash='0' * 64),
    lambda m, s: s['medical-2'].update(rawOutputHash='e' * 64),
    lambda m, s: s['normalize'].update(outputHash='0' * 64),
    lambda m, s: m.update(repairRounds=2),
])
def test_medical_retry_contract_rejects_changes(change):
    meta, stages = _medical_case()
    change(meta, stages)
    row = meta['medicalRetries'][0]
    row['proofHash'] = document_hash(row['proof'])
    with pytest.raises(ValueError):
        c.validate_medical_retries(meta, stages)


def test_runtime_revalidation_after_medical_retry_keeps_earlier_proofs_valid():
    meta, stages = _medical_case()
    ledger = {'identity': '3' * 64, 'pipelineVersion': c.POLICY, 'repairRounds': 3,
              'stages': {k: {kk: vv for kk, vv in v.items() if kk != 'name'} for k, v in stages.items()},
              'medicalRetries': meta['medicalRetries']}
    proof = {'priorLedger': ledger, 'priorLedgerHash': document_hash(ledger), 'packetHash': '2' * 64,
             'currentRuntimeHash': '5' * 64, 'reason': 'validator fix', 'toolSha256': '6' * 64, 'modelReplay': False}
    later = {**meta, 'runtimeHash': '5' * 64, 'runtimeRevalidations': [{'proof': proof, 'proofHash': document_hash(proof)}]}
    assert c.validate_runtime_revalidations(later, stages)
    assert c.validate_medical_retries(later, stages)
    changed = copy.deepcopy(stages)
    changed['normalize']['outputHash'] = '0' * 64
    with pytest.raises(ValueError):
        c.validate_runtime_revalidations(later, changed)
    with pytest.raises(ValueError):  # without the revalidation record the medical proof's runtime no longer matches
        c.validate_medical_retries({**meta, 'runtimeHash': '5' * 64}, stages)
