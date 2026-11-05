"""Resolve only explicit professor groups in the current notes filename."""
import re
import unicodedata


def from_sources(sources):
    names = []
    for source in sources:
        if source.get('kind') != 'notes_current':
            continue
        # The suffix after '_' is the note writer/version, never a professor.
        # The run ID itself contains an underscore: remove its prefix first.
        title = re.sub(r'^\[[^\]]+\]\s*', '', unicodedata.normalize('NFC', source.get('filename', ''))).split('_', 1)[0]
        for group in re.findall(r'\(([^()]*)\)', title):
            candidates = re.split(r'[·,/ㆍ\s]+', group.strip())
            if candidates and all(re.fullmatch(r'[가-힣]{2,4}', name) for name in candidates):
                names.extend(candidates)
    return list(dict.fromkeys(names))


def instruction(sources):
    names = from_sources(sources)
    return ('올해 담당 교수: ' + '·'.join(names) + ' (올해 필기 파일명 확인)' if names
            else '올해 담당 교수: 미확인. 동일 교수 기출 여부를 추정하지 않는다.')
