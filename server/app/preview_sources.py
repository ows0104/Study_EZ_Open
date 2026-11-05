"""Validate public notes provenance without importing the local runner."""
from __future__ import annotations

import hashlib
from sqlalchemy import select

from app.models import Asset, Preview
from studyez_contracts.preview_sources import professor_names, professor_text, validate


def preserve_binding(db, lecture, incoming):
    """A changed notes choice must not silently reattribute an existing conversation."""
    old = lecture.preview_source or {}
    binding = old.get('_previewBinding')
    preview = db.get(Preview, (lecture.subject, lecture.run_id))
    if binding is None and preview and preview.share_url:
        asset = db.scalar(select(Asset).where(Asset.subject == lecture.subject,
                          Asset.run_id == lecture.run_id, Asset.kind == 'notes_prev'))
        prior = old.get('selected') or {}
        binding = dict(filename=asset.filename if asset else '',
                       sha256=prior.get('sha256', '') if asset and prior.get('filename') == asset.filename else '')
    result = dict(incoming)
    for key in ('_previousAttachments', '_selectionHistory'):
        if key in old:
            result[key] = old[key]
    if old.get('fingerprint') and old['fingerprint'] != incoming['fingerprint']:
        result['_selectionHistory'] = [*old.get('_selectionHistory', []),
                                      {k: v for k, v in old.items() if not k.startswith('_')}]
    if binding is not None:
        result['_previewBinding'] = binding
    return result


def archive_attachment(lecture, asset, storage):
    """Keep the old immutable object and its restore information before retiring its row."""
    value = lecture.preview_source or {}
    previous = value.get('_previousAttachments', [])
    if any(row['objectKey'] == asset.object_key for row in previous):
        return
    source = storage.open_stream(asset.object_key)
    if source is None:
        raise ValueError('이전 예습 필기를 보존할 수 없어 교체를 보류합니다')
    chunks, _ = source
    digest = hashlib.sha256()
    size = 0
    for chunk in chunks:
        digest.update(chunk)
        size += len(chunk)
    if size != asset.size_bytes:
        raise ValueError('이전 예습 필기 크기가 달라 교체 전 확인이 필요합니다')
    entry = dict(id=asset.id, filename=asset.filename, objectKey=asset.object_key,
                 sizeBytes=size, sha256=digest.hexdigest(), contentType=asset.content_type,
                 uploadedAt=asset.uploaded_at.isoformat() if asset.uploaded_at else None)
    lecture.preview_source = {**value, '_previousAttachments': [*previous, entry]}


def bind_new_preview(lecture):
    value = lecture.preview_source
    if value and value.get('selected'):
        selected = value['selected']
        lecture.preview_source = {**value, '_previewBinding':
                                  dict(filename=selected['filename'], sha256=selected['sha256'])}


def public_source(lecture, event=None, assets=None):
    stored = lecture.preview_source
    if not stored:
        return None
    try:
        value = validate({k: v for k, v in stored.items() if not k.startswith('_')})
    except (ValueError, TypeError, KeyError):
        return None
    stale = (value['date'] != lecture.date.isoformat() or value['startTime'] != lecture.start_time
             or value['currentProfessors'] != professor_names(lecture.professors))
    if event and value['currentSource'] == 'timetable':
        stale |= (value['date'] != event.date.isoformat() or value['startTime'] != event.start_time
                  or value['currentProfessors'] != professor_text(event.professor))
    if stale:
        value.update(status='needs_review', changed=None, newProfessor=None,
                     reason='담당 또는 시간표가 바뀌어 자료 재확인 필요')
    selected = value['selected'] or {}
    binding = stored.get('_previewBinding')
    value['conversationNeedsReview'] = bool(binding is not None and
        (not binding.get('filename') or binding['filename'] != selected.get('filename')
         or binding.get('sha256') and binding['sha256'] != selected.get('sha256')))
    value['attachmentNeedsReview'] = False
    if assets is not None and selected:
        value['attachmentNeedsReview'] = not any(
            a.kind == 'notes_prev' and a.filename == selected['filename']
            and a.size_bytes == selected['sizeBytes'] for a in assets)
    return value


def preview_binding(lecture):
    return (lecture.preview_source or {}).get('_previewBinding') or {}
