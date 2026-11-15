# 선지: 사진 문항 그림 전달·작성·검토 기준 완화 — 구현 계획

## 변경 범위·대상 파일·순서
1. `quizbank/root_mcq.py`
   - 그림 파일 쓰기와 `images` 칸(작성·검토 입력).
   - `_stage`가 그림 경로를 호출에 넘긴다.
   - `_call`이 `codex.run(images=)`를 쓴다.
   - 검토 입력에 `lecture_facts`를 넣고, `REVIEW_POLICY`를 `mcq-medical/3`으로 바꾼다.
2. `content/prompts/learning-links/mcq/write.md`·`review.md`: 기준 완화와 그림 안내.
3. `tests/quizbank/test_root_mcq.py`: 그림이 파일·입력·호출로 가는지, 그림 없는 묶음은 그대로인지, 검토 입력에 강의 사실이 들어가는지.
4. 병합 → 러너 재설치 → 소아감염(261113_02) 재생성·업로드(`python -m runner.root_mcq --run-id 261113_02 --subject 감염과 면역`).

## 검사 명령과 성공 조건
- `python -m pytest tests/quizbank/test_root_mcq.py tests/runner/test_root_mcq_publish.py -q`
- 회귀: `python -m pytest tests/contracts tests/quizbank tests/runner -q`
  (바로가기 설치기의 기존 결함 1개는 이 변경과 무관하다)
- 재생성 뒤 확인:
  - 사진 문항 10개의 결과.
  - 빠진 문항 수(지금 42).
  - 운영 asset의 크기·시각.

## 위험·복원·승인할 범위
- 위험:
  - 기준이 느슨해져 정답으로 볼 수 있는 오답이 남을 수 있다.
  - 「목록 밖 실제 정답」 규칙은 그대로 두었고, 결과 표본을 읽어 확인한다.
- 복원: 병합 커밋 revert. 소아감염 asset은 남겨 둔 `v2-<revision>.json`을 `<revision>.json`으로 되돌려 `--upload-only`.
- 승인 범위:
  - 코드·지시문·검사·병합.
  - 러너 재설치.
  - 261113_02 한 편 재생성·업로드(사용자 「사진 넣어서 다시 만들어줘」·「소아감염 한 편만」).
  - 나머지 27편은 제외.
