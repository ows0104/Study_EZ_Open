# 감염병리1 Main-Quiz 새로 생성 — 구현 계획

## 변경 범위·대상 파일·순서
브랜치 `claude/infection-path1-resume`(origin/master 675a59e7에서 분기).
1. `studyez_contracts/bank/quality.py`: basic 복수 채점 단위 경고. 검사 `tests/quizbank/test_answer_quality.py`에 추가.
2. `studyez_contracts/roots/generation_v2.py` `repair_reasons`: 품질 경고를 `question_fix`로. 합성 검사 추가.
3. `content/prompts/learning-links/automation/author-v2.md`: 형식·한계·해설 지시 보강.
4. `runner/root_importance_review.py`: 자격 완화. `tests/quizbank/test_importance_chunks.py` 보강.
5. `docs/changes/2026-11-08-infection-path1-regen/run.py`: 실행 스크립트(새 폴더 id).
6. PR → master 병합(=API 자동 배포)은 사용자 승인 후. 실행은 병합된 master 코드로 한다(코드 지문이 실행 중 바뀌지 않게).
7. 실행(백그라운드, 승인 후): Map 1 → 포인트 1 → 정제(모델 4) → 생성·대조·정답 검수(보완 최대 3) → 중요도(갈래별 + 최종 대조 1) → 조립.
8. 격리 로컬(SQLite·로컬 저장소)에 등록해 풀이 화면 확인, 83문항 판·98문항 판과 숫자 비교 보고.

## 검사 명령과 성공 조건
- `python -m pytest tests/contracts tests/quizbank -q`, 루트 `pytest tests`(CI 제외 규칙 동일), `map_numbers --check`.
- 서버: `root_` 검사·`route_contract`(브랜치 계약을 PYTHONPATH로, 격리 sqlite).
- 기존 결과 호환: `runs/_examples/cholinergic-exception-20261105`와 공개 98문항 판 문서가 새 계약으로 그대로 검증되는지.
- 실행: 결과 `validate_result` 통과, 품질 errors 0, 성공 기준(intent) 숫자 보고.

## 위험·복원·승인할 범위
구현·검사·PR·master 병합(=되돌릴 수 있는 자동 배포)은 사용자 요청 「새로 다시 생성하는데, 품질 문제를 고치고
다시 돌리자」(2026-11-08)를 승인으로 보고 진행한다(개발 루프 「사람에게 묻는 것」 밖).
실행 직전에 따로 묻는 것(외부 전송·새 비용 대량 실행): S1 필기(sha 4b4229bc…, 37쪽)·S2 족보(sha 82ba65c6…, 27쪽)의 텍스트·페이지 이미지와
파생 결과를 OpenAI Codex CLI(gpt-6.1-sol)로 보내 7의 전 단계를 실행. 예상 모델 호출 약 20회, 수 시간.
비포함: 운영 등록·학생 공개·기존 판 교체·다른 강의 적용(각각 별도 승인).
복원: 병합 되돌리기(같은 자동 배포 경로). 실행 폴더는 git 밖에 새로 만들고 기존 폴더는 건드리지 않는다.
