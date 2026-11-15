# Main-Quiz 재배치가 바뀐 필기(같은 쪽 수)를 이어받기 — 구현 계획

## 변경 범위·대상 파일·순서
1. 쪽 비교 도우미(새 `quizbank/source_update.py`): 원본 짝, 쪽 수, 쪽별 텍스트·렌더 비교 → changedPages.
2. `quizbank/connection_replace.py`: 입력 비교를 「원본만 다름 + 같은 쪽 수」 허용으로, 공개 문서 원본 교체, manifest `sourceUpdate`, 로그.
3. 계약(spec R4): `roots/generation_v4.py` apply_source_update·`_judgments4`, `roots/validate.py` replaced_sources, `roots/media.py` 지문 그림 출처 sha.
4. 테스트: `tests/quizbank/test_connection_replace.py`, `tests/contracts`.
5. 실측(운영 쓰기 없음): 261112_03 이전 실행 폴더 + 새 packet(cfcfc136)으로 로컬 재생, 모델 단계는 이전 영수증 재사용·늦은 단계는 실제 호출 또는 생략.
6. Draft PR → 사용자 승인 뒤 병합 → 러너 재설치(한가할 때) → 261112_03 재요청 → 게시 뒤 기록 승계·근거 쪽 확인.

## 겹침
`connection_dedupe.py`(REQUEST_KEYS·lecture_input)·`runner/connection_generation.py`·서버 요청 경로는 Draft PR #194(존재 목표 보강)가 고치는 파일이다.
이 계획은 `connection_dedupe.py`를 고치지 않고 `connection_replace.py` 안에서 비교한다. 러너·서버는 변경 없음 예상. 확인 뒤 겹치면 조율.

## 검사 명령과 성공 조건
`pytest tests/contracts tests/quizbank tests/runner`(알려진 바로가기 실패 제외), 서버 `python -m tests root`. PR CI 통과.

## 위험·복원·승인할 범위
- 위험: 필기 수정이 문항 답에 닿아도 문항은 그대로다 — 바뀐 쪽의 문항을 결과에 적어 사람이 보게 한다(261112_03은 대조 완료: 고칠 문항 없음).
- 복원: 공개 판을 이전 판으로 되돌림. 기록은 어느 판에도 남는다.
- 승인 범위: 1~5 구현·실측·Draft PR. 병합·러너 재설치·운영 재요청은 각각 승인.
