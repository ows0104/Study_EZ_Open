# Main-Quiz 선지를 게시 직후 기본 실행 — 배포 준비

## 코드 리뷰·검증 결과
2026-11-14 클라우드 세션(Linux, Python 3.13):
- `pytest tests/runner`(CI 범위): 810 중 808 통과. 실패 2(`test_desktop_control.py::test_existing_agent_is_connected_without_launch`,
  `test_process_query_failure_does_not_launch`)는 이 컨테이너에 tkinter가 없어서이며 master에서도 같은 2개가 실패한다(변경 전 stash로 확인).
- 선지 관련 검사(`test_root_choices_publish`·`test_connection_generation`·`test_dedupe_published_runner`·`test_root_front`·`test_root_front_v3`) 통과.

## 배포 대상 버전·순서·데이터 변경
- 러너만 바뀐다. 서버·웹·DB 변경 없음 → master 병합으로 API·웹이 다시 배포돼도 동작은 같다.
- 운영 반영: 사용자 PC에서 병합 커밋으로 `.runtime/main-quiz-<sha12>`를 설치하고 도는 작업이 없을 때 에이전트를 교체한다.

## 배포 후 확인·롤백·필요한 사람 승인
- 확인: 다음 Main-Quiz 게시 로그에 `단답·나열 선지 작성` → `선지 업로드 완료`, 그 강의 풀이 화면에서 「선지 보기」.
- 빠진 강의 보강(사용자 PC 저장소 사본): `python -m runner.root_choices --all-published --subject 감염과 면역 --missing`.
  이미 올린 강의는 모델 호출 없이 「이미 올림 — 건너뜀」으로 찍힌다.
- 롤백: 병합 커밋 revert 후 러너 재설치.
