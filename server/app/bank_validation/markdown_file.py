"""Dependency-free validation of the authored Markdown file transport."""
from __future__ import annotations
import hashlib
import json
import re

MAX_BYTES = 8_000_000
MARK = 'STUDYEZ_BANK_COMPLETE'


def validate(raw: str, filename: str, subject: str, run_id: str, metadata: dict | None = None) -> dict:
    def require(condition, message):
        if not condition:
            raise ValueError(message)

    require(isinstance(raw, str) and 200 <= len(raw) <= 2_000_000, '문제은행 파일의 길이가 올바르지 않습니다.')
    require(filename.endswith('.md') and run_id in filename and not re.search(r'[\\/\x00-\x1f]', filename), '선택한 강의 ID가 포함된 .md 파일을 사용하세요.')
    data = raw.encode('utf-8')
    require(len(data) <= MAX_BYTES, '문제은행 파일이 너무 큽니다.')
    text = raw.removeprefix('\ufeff').replace('\r\n', '\n')
    header = re.match(r'<!-- STUDYEZ_BANK_FILE (\{[^\n]+\}) -->\n', text)
    require(header is not None, '파일 첫 줄의 STUDYEZ_BANK_FILE 정보가 없습니다.')
    try:
        info = json.loads(header[1])
    except (ValueError, TypeError) as exc:
        raise ValueError('문제은행 파일 정보가 올바른 JSON이 아닙니다.') from exc
    require(isinstance(info, dict) and type(info.get('schema_version')) is int and info.get('schema_version') == 1 and info.get('run_id') == run_id
            and info.get('subject') == subject, '파일의 강의 ID·과목이 선택한 강의와 다릅니다.')
    require(isinstance(info.get('prompt_version'), str) and re.fullmatch(r'\d+\.\d+', info['prompt_version']), '프롬프트 버전이 없습니다.')
    require(text.rstrip().endswith(MARK) and len(re.findall(r'^STUDYEZ_BANK_COMPLETE[ \t]*$', text, re.M)) == 1, '파일 끝의 완료 표식이 없거나 중복됐습니다.')
    body = text[header.end():].rstrip()[:-len(MARK)]
    headings = list(re.finditer(r'^### (Q\d+|CF\d+)(?:[ \t]*\|([^\n]+))?[ \t]*$', body, re.M))
    ids = [h[1] for h in headings if h[1].startswith('Q')]
    conflicts = [h[1] for h in headings if h[1].startswith('CF')]
    require(type(info.get('question_count')) is int and info['question_count'] == len(ids) and ids
            and info.get('question_ids') == ids and ids == [f'Q{i:03}' for i in range(1, len(ids) + 1)], '전체 문항 수·ID 목록이 실제 파일과 다르거나 누락·중복됐습니다.')
    require(info.get('conflict_ids') == conflicts and len(set(conflicts)) == len(conflicts), '출처 충돌 ID 목록이 실제 파일과 다릅니다.')
    used_conflicts = set()

    def parse(value):
        value = (value or '').strip()
        if value.startswith('`') and value.endswith('`'):
            value = value[1:-1]
        try:
            return json.loads(value)
        except (ValueError, TypeError) as exc:
            raise ValueError('파일의 정답·해설·근거 JSON이 올바르지 않습니다.') from exc

    def entries(value):
        rows = re.findall(r'^\s*([A-Z]+|\d+)\.\s+.+$', value or '', re.M)
        require(rows and len(set(rows)) == len(rows), '보기 항목이 없거나 ID가 중복됐습니다.')
        return rows

    for i, heading in enumerate(headings):
        if not heading[1].startswith('Q'):
            continue
        block = body[heading.end():headings[i + 1].start() if i + 1 < len(headings) else len(body)]
        matches = list(re.finditer(r'^(문제|정답|출처|출제근거|근거|심화|해설|충돌|보기|왼쪽|오른쪽|항목):[ \t]*(.*)$', block, re.M))
        fields = {}
        for j, match in enumerate(matches):
            require(match[1] not in fields, f'중복 필드: {match[1]}')
            fields[match[1]] = block[match.start() + len(match[1]) + 1:matches[j + 1].start() if j + 1 < len(matches) else len(block)].strip()
        f = fields
        fmt = (heading[2] or '').split('|')[0].strip()
        require(fmt in ('basic', 'list', 'ox', 'cloze', 'mcq', 'multi_select', 'matching', 'sequence'), f'{heading[1]}의 문항 형식이 없습니다.')
        require(all(f.get(key) for key in ('문제', '출처', '출제근거', '근거')) and f.get('심화') in ('true', 'false'), f'{heading[1]}의 필수 필드가 빠졌습니다.')
        require(isinstance(parse(f['근거']), dict), '근거는 JSON 객체여야 합니다.')
        if f.get('해설'):
            require(isinstance(parse(f['해설']), str), '해설은 JSON 문자열이어야 합니다.')
        if f.get('충돌'):
            require(f['충돌'] in conflicts, '정의되지 않은 충돌 ID를 참조했습니다.')
            used_conflicts.add(f['충돌'])
        if fmt == 'cloze':
            require(not f.get('정답') and re.search(r'(?<!\{)\{[^{}\n]+\}(?!\})', f['문제']), '빈칸 또는 정답 형식을 확인하세요.')
            continue
        answers = parse(f.get('정답'))
        require(isinstance(answers, list) and answers and all(isinstance(a, str) and a.strip() for a in answers), '정답 배열이 없습니다.')
        if fmt == 'basic':
            require(len(answers) == 1, '단답형의 정답 단위를 확인하세요.')
        if fmt == 'ox':
            require(answers in (['O'], ['X']) and f.get('해설'), 'OX 정답과 해설을 확인하세요.')
        if fmt in ('mcq', 'multi_select', 'sequence'):
            options = entries(f.get('항목' if fmt == 'sequence' else '보기'))
            require(len(set(answers)) == len(answers) and all(a in options for a in answers)
                    and (fmt != 'mcq' or len(answers) == 1)
                    and (fmt != 'sequence' or len(answers) == len(options)), '정답이 실제 보기·순서 항목과 맞지 않습니다.')
        if fmt == 'matching':
            left, right = entries(f.get('왼쪽')), entries(f.get('오른쪽'))
            pairs = [re.fullmatch(r'(\d+)-([A-Z]+)', a) for a in answers]
            require(all(p and p[1] in left and p[2] in right for p in pairs)
                    and len(pairs) == len(left) and len({p[1] for p in pairs if p}) == len(left), '정답 짝이 실제 항목과 맞지 않습니다.')
    require(used_conflicts == set(conflicts), '문항에서 사용하지 않은 출처 충돌 기록이 있습니다.')
    result = {'filename': filename, 'sha256': hashlib.sha256(data).hexdigest(), 'byteLength': len(data),
              'subject': subject, 'runId': run_id, 'promptVersion': info['prompt_version'],
              'questionCount': len(ids), 'questionIds': ids, 'conflictIds': conflicts, 'validated': True}
    if metadata is not None:
        require(metadata.get('sha256') == result['sha256'] and metadata.get('byteLength') == len(data), '파일의 SHA-256·바이트 수가 실제 내용과 다릅니다.')
    return result
