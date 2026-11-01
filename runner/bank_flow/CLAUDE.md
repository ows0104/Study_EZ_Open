# 은행 처리 러너 읽기 지도

runner/CLAUDE.md와 전체 개발 루프를 따른다. CLI는 기존 `python -m runner bank`이며
runner/bank.py는 호출자 import 호환 진입점이다. 새 코드와 mock은 아래 실제 소유 모듈을 사용한다.

| 변경할 책임 | 시작 파일 | 확인할 계약 |
|---|---|---|
| 처리 순서·생성기 인수·종료 판정 | execution.py | 저장된 웹 응답만 처리, 기존 run_forwarded 사용 |
| 첨부 PDF·족보 조각 캐시 | sources.py | 붙였던 판 유지, 파일명 NFC, 교수·pin revision 캐시 |
| 재개 여부·남은 수정 횟수·진단 | state.py | 응답/자료 해시·build ID·경로·상한 검증 |
| 실패 보고·이미지·은행 업로드 | upload.py | respondedAt/baseBuildId, 파일 확인 후 은행 PUT |
| HTTP·인증·MIME·파일 재시도 | ../transport.py | API 토큰과 서명 URL 헤더 분리, 3회 재시도 |

execution은 sources/state/upload를 조합한다. state는 HTTP와 프로세스에 의존하지 않는다.
upload는 transport와 state만 사용하며 모델을 실행하지 않는다.
sources의 PDF fallback은 기존 publish.plan_subject를 호출한다. publisher가 족보 조각을
사용하므로 이 한 의존성은 호출 시점에 가져와 import 순환 초기화를 피한다.
기존 deck 자료 기능은 quizgen.build 등의 보조 코드를 간접 import한다. 이 호환 의존성은
이번에 유지하며 생성 실행은 여전히 하위 프로세스로 한다. transport는 이 의존성 없이 import된다.

실제 runs 파일을 구조 정리를 위해 변경하거나 재생성하지 않는다. response-resume.json,
resume.json, jokbo.json, 남은 수정 횟수, 원문 바이트 및 로그 접두사를 유지한다.
업로드가 끝났다는 로그는 agent.finish_bank가 사용하므로 문구를 임의로 바꾸지 않는다.

검사: `python -m pytest tests/runner/test_bank.py tests/runner/test_transport.py -q`.
실행/상태 경계 변경은 `tests/runner` 전체를 추가 확인한다. 실제 모델·운영 서버로 검사하지 않는다.
