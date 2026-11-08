# 구현 계획
변경 파일:
- `studyez_contracts/roots/generation_v2.py`: CONTEXT·medical_question_hash·validate_medical_reuse·validate_result
- `quizbank/connection_generate_v2.py`: 단계 잠금·context 단계·동시 실행·재사용 호출·manifest
- `runner/root_native_json.py`: context 단계의 schema·task·check
- `content/prompts/learning-links/automation/context-v2.md`
- Map 실행 스크립트의 packet `speedStages: true`

검사:
- 새 `tests/quizbank/test_root_speed.py` 3개
- native context 1개
- 루트 `pytest tests`·`map_numbers --check`
- 서버 root_·route_contract

구현·검사·PR·병합은 사용자 요청으로 진행한다. 운영 DB 변경은 없다.
