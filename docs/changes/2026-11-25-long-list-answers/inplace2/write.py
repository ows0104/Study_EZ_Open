"""운영 쓰기(사용자 확인 뒤에만): apply.py·verify.py를 통과한 사본을 같은 판 그대로 제자리에 넣는다.

강의마다 세 단계, 단계마다 한 트랜잭션(pooler가 여러 MB 묶음 쓰기를 끊는다). 다시 돌리면 끝난 단계는 건너뛴다.
1. asset(root_mcq·root_order·root_evidence): 새 R2 키(`….term-20261124.json`)에 올리고 asset 행의 키·크기만 바꾼다.
   옛 R2 파일은 지우지 않는다(되돌릴 때 키만 되돌리면 된다).
2. root_content: document·digest·light(그림 뺀 사본과 지문). 판·과제·문항 ID는 그대로 — 기록은 task_id로 이어진다.
3. root_generation: result.document를 같은 새 문서로, result_digest를 다시 계산(보강·교체 검사가 공개판과 비교한다).
쓰기 전에 운영 값이 백업(before/meta.json)과 같은지 확인하고, 다르면 그 강의는 멈춘다.
"""
import hashlib
import io
import json
import sys
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(r'C:\Users\ows01\Documents\Python Scripts\Study_EZ_Open\server\.env')
from sqlalchemy import select

from app.database import SessionLocal
from app.models.lectures import Asset
from app.models.root_generation import RootGeneration
from app.models.root_learning import RootContent, RootControl
from app.root_learning.light import stored
from app.storage import ObjectStorage
from studyez_contracts.roots import document_hash

WORK = Path(r'C:\Users\ows01\Documents\Python Scripts\Study_EZ_Open\runs\_development\2026-11-25-long-list-answers/inplace2')
SUFFIX = '.split-20261125.json'


def load(path):
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else None


def write(rid, receipt):
    meta = load(WORK / rid / 'before/meta.json')
    after = WORK / rid / 'after'
    doc, result = load(after / 'document.json'), load(after / 'generation-result.json')
    subject, revision = meta['subject'], meta['revision']
    new_digest = document_hash(doc)
    store = ObjectStorage()
    log = {'runId': rid, 'revision': revision, 'assets': {}}

    with SessionLocal() as db:
        control = db.get(RootControl, (subject, rid))
        assert control.revision == revision, (rid, '공개판이 바뀌었다', control.revision)
        for kind in ('root_mcq', 'root_order', 'root_evidence'):
            before_meta = meta['assets'].get(kind)
            new_bytes = (after / f'{kind}.json').read_bytes() if (after / f'{kind}.json').exists() else None
            if before_meta is None or new_bytes is None:
                continue
            if new_bytes == (WORK / rid / f'before/{kind}.json').read_bytes():
                log['assets'][kind] = 'unchanged'
                continue
            asset = db.get(Asset, before_meta['id'])
            new_key = before_meta['object_key'].removesuffix('.json') + SUFFIX
            if asset.object_key == new_key:
                log['assets'][kind] = 'already'
                continue
            assert asset.object_key == before_meta['object_key'] and asset.size_bytes == before_meta['size_bytes'], (rid, kind, 'asset이 바뀌었다')
            store.upload_fileobj(io.BytesIO(new_bytes), new_key, content_type=before_meta['content_type'])
            assert store.get_bytes(new_key) == new_bytes, (rid, kind, '올린 파일 확인 실패')
            asset.object_key, asset.size_bytes = new_key, len(new_bytes)
            db.commit()
            log['assets'][kind] = {'from': before_meta['object_key'], 'to': new_key,
                                   'sha256': hashlib.sha256(new_bytes).hexdigest()}

    with SessionLocal() as db:
        row = db.get(RootContent, (subject, rid, revision))
        if row.digest == new_digest:
            log['content'] = 'already'
        else:
            assert row.digest == meta['digest'], (rid, 'root_content가 바뀌었다')
            row.document, row.digest, row.light = doc, new_digest, stored(doc)
            db.commit()
            log['content'] = {'digestBefore': meta['digest'], 'digestAfter': new_digest}

    with SessionLocal() as db:
        gen = db.get(RootGeneration, meta['generationId'])
        new_result_digest = document_hash(result)
        if gen.result_digest == new_result_digest:
            log['generation'] = 'already'
        else:
            assert gen.result_digest == meta['resultDigest'], (rid, 'root_generation이 바뀌었다')
            gen.result, gen.result_digest = result, new_result_digest
            db.commit()
            log['generation'] = {'digestBefore': meta['resultDigest'], 'digestAfter': new_result_digest}

    with receipt.open('a', encoding='utf-8') as handle:
        handle.write(json.dumps(log, ensure_ascii=False) + '\n')
    return log


if __name__ == '__main__':
    receipt = WORK / 'receipt.jsonl'
    for rid in sys.argv[1:]:
        print(json.dumps(write(rid, receipt), ensure_ascii=False), flush=True)
