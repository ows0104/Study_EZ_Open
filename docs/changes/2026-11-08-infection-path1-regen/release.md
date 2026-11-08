# 감염병리1 Main-Quiz 새로 생성 — 품질 측정을 보완 루프에 연결 — 배포 준비

## 코드 리뷰·검증 결과

- `studyez_contracts/bank/quality.py`: basic인데 채점 단위 2개 이상이면 경고(warning만, 문항을 떨어뜨리지 않음).
- `studyez_contracts/roots/generation_v2.py` `quality_reasons`: 품질 경고를 `question_fix` 보완 사유로.
  `repair_reasons`가 붙인다. 보완 상한 3회는 그대로이고 계약 검증(`validate_result`)은 보완 사유를 다시 계산하지 않으므로
  기존 결과의 검증은 바뀌지 않는다.
- `content/prompts/learning-links/automation/author-v2.md`: basic 정답 하나, 여러 항목은 list·cloze 표·객관식·분할,
  긴 정답의 부연은 해설로, 「문항 품질」 보완 사유를 실제 형식·분할로 고칠 것.
- `runner/root_importance_review.py`: 자격을 「수정 3/3 소진」에서 「모든 단계 완료·결과 없음·다음 원본 대조 없음」으로.
  계약 쪽은 이미 최종 회차 n을 일반으로 받는다.
- 실행 스크립트 `run.py`: 이전 `2026-11-08-infection-path1-map/run.py`의 사본, 실행 폴더 `runs/_e2e/26110802`와 revision만 다름.

측정(읽기 전용, 새 코드):
- 운영 Quiz Bank 35편: 새 basic 단위 경고 6개(261001_03 3, 261007_02·261008_02·261008_03 각 1). errors 증가 0.
- 공개 98문항 판: errors 0 · warnings 38(basic 단위 8). 83문항 판: errors 1 · warnings 101(basic 단위 62).

검사:
- 루트 `pytest tests`: 2,136 통과·3 건너뜀. 제외 1건은 `test_desktop_control` 바로가기 설치기(origin/master에서도 같은 실패).
- `scripts/map_numbers --check` 정상.
- 서버(브랜치 계약을 `PYTHONPATH`로, 파일별 격리 sqlite): 아래 「서버 검사」에 기록.

## 배포 대상 버전·순서·데이터 변경

master 병합 → Actions가 검사 → API(Cloud Run) → 웹(Pages) 자동 배포. server/·web/ 파일 변경 없음.
API는 같은 `validate_bank`로 Quiz Bank 업로드를 검증하므로 관리자 화면 issues에 basic 단위 경고가 새로 보일 수 있다(문항은 그대로).
DB·운영 문항·학습 기록·수정 상한 변경 없음.

## 배포 후 확인·롤백·필요한 사람 승인

배포 영수증·API health SHA 확인. 롤백은 병합 되돌리기.
감염병리1 새 생성(외부 모델 전송·대량 실행)은 실행 직전에 범위를 정해 사용자 승인을 받는다.
운영 등록·학생 공개·기존 판 교체는 별도 승인.
