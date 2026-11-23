"""Main-Quiz 강의 문항 전체 보기(docs/changes/2026-11-23-lecture-question-list).

한 판의 문항을 한 화면에 펼치는 읽기 전용 목록. 가벼운 사본(light.py)만 읽는다 — 그림 바이트·R2 서명·근거 asset은
읽지 않고, 참고 슬라이드는 쪽 번호만 둔다. 슬라이드·그림은 화면이 한 문항을 누를 때 상세 API가 불러온다.
"""
from studyez_contracts.bank.pages import pages_of
from app.root_learning import content


def reference_pages(document, q):
    """이 문항이 인용한 쪽: 강의록·족보 원본별 PDF 쪽 번호(중복·범위 밖 제외). 순서는 인용 순."""
    sources = {s['source_id']: s for s in document.get('review', {}).get('sources', [])}
    refs = list(q.get('source_refs', [])) + [{'source_id': s.get('source_id'), 'pages': [s.get('page')]}
                                               for s in q.get('stimuli', []) if s.get('source_id')]
    out, seen = [], set()
    for ref in refs:
        sid = ref.get('source_id')
        source = sources.get(sid)
        if source is None:
            continue
        count = source.get('page_count')
        for page in ref.get('pages') or pages_of(ref.get('locator', '')):
            if type(page) is not int or page < 1 or (type(count) is int and page > count) or (sid, page) in seen:
                continue
            seen.add((sid, page))
            out.append({'sourceId': sid, 'page': page, 'exam': source.get('kind') == 'exam'})
    return out


def row(document, q, planned):
    """한 문항의 목록 행. 앞면은 풀이 화면과 같은 허용 목록(content.front)에서 그림만 뺀다."""
    figures = len(q.get('stimuli') or [])
    front = content.front({**q, 'stimuli': []})
    return {'question': {**front, 'figures': figures}, 'answer': content.answer(q),
            'pages': reference_pages(document, q), 'planned': q['question_id'] in planned}


def rows(document, current):
    """판 문서 순서의 행. `current`: 문항 → 내게 보이는 문항(개인 수정·내 중요도 반영)."""
    planned = {t['question_id'] for t in document['tasks']}
    return [row(document, current(q), planned) for q in document['bank_snapshot']['questions']]


def sources(document):
    """화면이 쪽 번호 옆에 붙이는 원본 이름(판 문서의 검토 기록 label)."""
    return [{'sourceId': s['source_id'], 'exam': s.get('kind') == 'exam', 'label': s.get('label') or s['source_id']}
            for s in document.get('review', {}).get('sources', [])]
