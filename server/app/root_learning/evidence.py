"""Read-only question evidence, bound to the exact authored source snapshots."""
from studyez_contracts.bank.pages import pages_of
from studyez_contracts.roots import document_hash
from app.models import QuizBank
from app.storage import ObjectStorage


def attach_evidence(db, doc, question, generation, answer):
    if doc.document['bank_source'] == 'quizbank':
        row = db.get(QuizBank, (doc.subject, doc.run_id))
        if row and row.build_id == doc.document['bank_build_id'] and document_hash(row.bank) == doc.document['review']['bank_sha256']:
            from app.routes.bank_api.presentation import _slides, _jokbo_slides
            answer['slides'] = _slides(db, row, question['question_id'])
            answer['jokboSlides'] = _jokbo_slides(db, row, question)
    if generation is None:
        return
    from app.root_learning.reviewed_import import source_records
    sources = source_records(generation)
    storage = ObjectStorage()
    known = {s['source_id']: s for s in doc.document['review']['sources']}
    signed = {}
    answer['sourceLinks'] = []
    for source in sources:
        expected = known.get(source['id'])
        if not expected or expected['sha256'] != source['sha256']:
            continue
        is_pdf = source.get('contentType') == 'application/pdf' or source['filename'].lower().endswith('.pdf')
        url = storage.presign_download(source['snapshotKey'], filename=source['filename'],
            inline=is_pdf, content_type='application/pdf' if is_pdf else None)
        answer['sourceLinks'].append({'label': source['filename'], 'url': url})
        if is_pdf:
            signed[source['id']] = (source, url)
    references = list(question.get('source_refs', [])) + [
        {'source_id': s['source_id'], 'pages': [s['page']]} for s in question.get('stimuli', [])]
    slides = {}
    for ref in references:
        pair = signed.get(ref['source_id'])
        if pair is None:
            continue
        source, url = pair
        pages = ref.get('pages') or pages_of(ref.get('locator', ''))
        count = source.get('pageCount') or source.get('page_count') or known[source['id']].get('page_count')
        for page in pages:
            if type(page) is not int or page < 1 or (type(count) is int and page > count):
                continue
            slides[(source['id'], page)] = {'sourceId': source['id'], 'sourceSha256': source['sha256'],
                'sourceFilename': source['filename'], 'page': page, 'url': url}
    answer['pdfSlides'] = list(slides.values())
