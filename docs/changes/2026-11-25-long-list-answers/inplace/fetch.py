"""운영에서 읽기만: 공개판 문서·생성 기록·선지/순서/근거 asset을 받아 runs/_development/...에 둔다(백업 겸 작업 원본)."""
import json, os, sys
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(r'C:\Users\ows01\Documents\Python Scripts\Study_EZ_Open\server\.env')
from sqlalchemy import select
from app.database import SessionLocal
from app.models.root_learning import RootContent, RootControl
from app.models.root_generation import RootGeneration
from app.models.lectures import Asset
from app.storage import ObjectStorage

OUT = Path(r'C:\Users\ows01\Documents\Python Scripts\Study_EZ_Open\runs\_development\2026-11-25-long-list-answers/inplace')
RUNS = sys.argv[1:] or ['261123_01', '261123_02', '261123_03', '261123_05', '261123_06', '261123_07']
store = ObjectStorage()
with SessionLocal() as db:
    db.connection().exec_driver_sql('SET TRANSACTION READ ONLY')
    for rid in RUNS:
        control = db.scalar(select(RootControl).where(RootControl.run_id == rid))
        subject, revision = control.subject, control.revision
        row = db.get(RootContent, (subject, rid, revision))
        gid = revision.removeprefix('auto-')
        gen = db.get(RootGeneration, gid)
        folder = OUT / rid / 'before'
        folder.mkdir(parents=True, exist_ok=True)
        meta = {'subject': subject, 'runId': rid, 'revision': revision, 'digest': row.digest, 'reviewed': row.reviewed,
                'lightIsNull': row.light is None, 'generationId': gen.id if gen else None,
                'resultDigest': gen.result_digest if gen else None,
                'resultDocumentIsPublished': bool(gen and gen.result and gen.result.get('document') == row.document), 'assets': {}}
        (folder / 'document.json').write_text(json.dumps(row.document, ensure_ascii=False), encoding='utf-8')
        if gen and gen.result is not None:
            (folder / 'generation-result.json').write_text(json.dumps(gen.result, ensure_ascii=False), encoding='utf-8')
        for kind in ('root_mcq', 'root_order', 'root_evidence'):
            asset = db.scalar(select(Asset).where(Asset.subject == subject, Asset.run_id == rid, Asset.kind == kind,
                                                  Asset.filename == f'{revision}.json'))
            if asset is None:
                meta['assets'][kind] = None
                continue
            body = store.get_bytes(asset.object_key)
            (folder / f'{kind}.json').write_bytes(body)
            meta['assets'][kind] = {'id': asset.id, 'object_key': asset.object_key, 'size_bytes': asset.size_bytes,
                                    'uploaded_at': str(asset.uploaded_at), 'content_type': asset.content_type, 'bytes': len(body)}
        (folder / 'meta.json').write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding='utf-8')
        print(rid, revision, 'doc', round(len(json.dumps(row.document)) / 1e6, 1), 'MB',
              'gen', bool(gen), 'resultIsPublished', meta['resultDocumentIsPublished'],
              {k: (v and v['bytes']) for k, v in meta['assets'].items()}, flush=True)
    db.rollback()
