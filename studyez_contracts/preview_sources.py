"""Public, path-free provenance for professor-aware preview notes."""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata


def professor_names(names):
    return sorted({re.sub(r'\s+', '', unicodedata.normalize('NFC', name))
                   for name in names if isinstance(name, str) and name.strip()})


def professor_text(value):
    return professor_names(re.split(r'[,·/\n、;]+', value or ''))


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(',', ':')).encode()).hexdigest()


def conversation_matches(source, filename='', sha256=''):
    selected = source.get('selected') or {}
    expected = filename or source.get('baselineFilename', '')
    if not selected:
        return False
    if expected:
        return expected == selected['filename'] and (not sha256 or sha256 == selected['sha256'])
    return selected['year'] == source['baselineYear']


def validate(value):
    """Whitelist every field; reject accidental paths and malformed producer data."""
    if not isinstance(value, dict):
        raise ValueError('예습 자료 정보가 객체여야 합니다')
    fields = {'version', 'year', 'currentProfessors', 'currentSource', 'date', 'startTime',
              'baselineYear', 'baselineProfessors', 'baselineFilename', 'changed',
              'newProfessor', 'status', 'reason', 'coverage', 'selected', 'fingerprint'}
    if set(value) != fields or type(value['version']) is not int or value['version'] != 1:
        raise ValueError('지원하지 않는 예습 자료 계약')
    year = value['year']
    if type(year) is not int or not 2000 <= year <= 2200:
        raise ValueError('예습 기준 연도 확인 필요')
    if value['currentSource'] not in ('notes', 'timetable') or value['status'] not in ('ok', 'needs_review'):
        raise ValueError('예습 담당 출처/상태 확인 필요')
    for name in ('currentProfessors', 'baselineProfessors'):
        if not isinstance(value[name], list) or value[name] != professor_names(value[name]):
            raise ValueError('교수 이름 확인 필요')
    for name in ('changed', 'newProfessor'):
        if value[name] is not None and type(value[name]) is not bool:
            raise ValueError('교수 비교 상태 확인 필요')
    if type(value['baselineYear']) is not int or value['baselineYear'] >= year:
        raise ValueError('직전 자료 비교 연도 확인 필요')
    for name in ('date', 'startTime', 'reason', 'baselineFilename', 'fingerprint'):
        if not isinstance(value[name], str) or len(value[name]) > 1000:
            raise ValueError('예습 자료 문자열 확인 필요')
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value['date']) or not re.fullmatch(r'\d{2}:\d{2}', value['startTime']):
        raise ValueError('예습 대상 날짜/시각 확인 필요')
    if not re.fullmatch(r'[a-f0-9]{64}', value['fingerprint']):
        raise ValueError('예습 자료 지문 확인 필요')
    coverage = value['coverage']
    if not isinstance(coverage, dict) or set(coverage) != {'available', 'missing', 'incomplete', 'failed'}:
        raise ValueError('검색 연도 확인 필요')
    window = set(range(year - 5, year))
    for years in coverage.values():
        if not isinstance(years, list) or any(type(y) is not int or y not in window for y in years) or len(years) != len(set(years)):
            raise ValueError('최근 5년 검색 범위 확인 필요')
    available, missing, failed = (set(coverage[k]) for k in ('available', 'missing', 'failed'))
    if available | missing | failed != window or available & missing or available & failed or missing & failed:
        raise ValueError('검색 연도 누락/중복')
    if not set(coverage['incomplete']) <= available:
        raise ValueError('미해석 자료 연도 확인 필요')
    if value['baselineFilename'] and any(s in value['baselineFilename'] for s in ('/', '\\', ':')):
        raise ValueError('예습 원본 경로를 공개할 수 없습니다')
    selected = value['selected']
    if selected is not None:
        if not isinstance(selected, dict) or set(selected) != {'year', 'filename', 'professors', 'sha256', 'sizeBytes', 'match'}:
            raise ValueError('선택 필기 정보 확인 필요')
        if type(selected['year']) is not int or selected['year'] >= year:
            raise ValueError('선택 필기 연도 확인 필요')
        if selected['match'] not in ('same', 'partial', 'different', 'unknown'):
            raise ValueError('교수 일치 상태 확인 필요')
        if not isinstance(selected['filename'], str) or not selected['filename'] or any(s in selected['filename'] for s in ('/', '\\', ':')):
            raise ValueError('예습 원본 경로를 공개할 수 없습니다')
        if not isinstance(selected['professors'], list) or selected['professors'] != professor_names(selected['professors']):
            raise ValueError('선택 필기 교수 확인 필요')
        if not isinstance(selected['sha256'], str) or not re.fullmatch(r'[a-f0-9]{64}', selected['sha256']):
            raise ValueError('선택 필기 해시 확인 필요')
        if type(selected['sizeBytes']) is not int or selected['sizeBytes'] < 0:
            raise ValueError('선택 필기 크기 확인 필요')
        if selected['match'] == 'same' and selected['year'] not in window:
            raise ValueError('동일 교수 예습은 최근 5년 자료여야 합니다')
        teachers, old = value['currentProfessors'], selected['professors']
        expected = ('unknown' if not teachers or not old else 'same' if teachers == old
                    else 'partial' if set(teachers) & set(old) else 'different')
        if selected['match'] != expected or selected['match'] == 'same' and value['newProfessor'] is True:
            raise ValueError('교수 일치 판정과 담당 정보가 다릅니다')
    return json.loads(json.dumps(value, ensure_ascii=False))
