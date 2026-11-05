# 연결 중심 학습과 구조·시험·임상 중요도 구분 — 배포 준비

## 코드 리뷰·검증 결과
단계 A 로컬 구현 완료. `studyez_contracts/learning_links/`의 순수 계약·지문·대조 검증, `quizbank.connection_plan`의 입력 보존/새 폴더 출력, `connection_report`의 검토 보고서, 입력 안내와 합성 검사를 구현했다. 기존 BANK/PLAN/REPORT·운영 프롬프트·문항·학습 기록은 수정하지 않았다.

최종 검사 근거는 state.json의 같은 source_hash `77971c5833a4a744397699e3f150e742f110285f56e4eec474e217bc87c6638c`와 plan_hash에 결부돼 있다.

| 검사 | 실제 결과 | 로그 |
|---|---|---|
| link-contract | 39 passed | runs/_development/2026-11-02-connection-first-design/1793597596926437700-link-contract.log |
| link-package | 15 passed | runs/_development/2026-11-02-connection-first-design/1793597599825191900-link-package.log |
| generation-regression | 108 passed | runs/_development/2026-11-02-connection-first-design/1793597604691214400-generation-regression.log |

신규 검사는 54개이며 회귀 108개에는 신규 계약 39개가 포함돼 있다. 서로 다른 검사 사례는 총 123개다. 초기 기본 임시 폴더 생성 실패는 작업 폴더 안의 고유 임시 경로로 해결했다. 문항별 관계 일관성 보강 뒤 기존 테스트가 더 이른 오류를 만나 실패한 사례는 입력을 일관되게 고쳐 의도한 회상 검사를 검증했다. 초기 회귀는 108개가 통과했으나 검사 중 공통 입력 지문 변경으로 근거 코드 2가 기록됐고, 최종에는 동일 지문으로 재검사했다. 실패 이력은 삭제하지 않았다.

코드 리뷰에서 참조·중복·범위·판 불일치, 문항의 여러 대응 사이 관계 역할 모순, 부분 방향과 전체 충족 구분, unknown/gap 구분, 입력 전후 지문, 출력 덮어쓰기/중간 실패, Markdown/HTML 데이터 이스케이프, 공용 패키지 등록, 기존 검수·충돌 표시를 확인했다. 사람이 읽는 [최종 합성 보고서](example-final/review.md)와 complete.json의 출력 해시를 확인했다. 앞선 example-package/example-package-v1은 중간 출력으로 보존하며 최종 예시는 example-final이다.

의미 판정의 참/거짓·실제 PDF 쪽수·독립 추출 provenance의 진위는 구조 검사로 인증하지 않는다. 현재 예시는 A/B/C/D 합성 자료이며 실제 강의의 검토·재출제가 아니다.

## 배포 대상 버전·순서·데이터 변경
Git 기준 HEAD는 `138f32dc432bbc54ed2e71604363782d28dd1014`이며 이 작업은 미커밋 로컬 변경이다. 전체 작업 공간에는 다른 작업의 변경이 있어 이를 혼합한 커밋/운영 후보를 만들지 않았다. 실제 구현 파일/계약 판과 입력 지문은 최종 예시 manifest.json, 전체 영역의 검사 지문은 state.json을 따른다.

단계 A는 로컬 명령으로만 사용한다. DB 마이그레이션·API·웹 화면·서버 배포·자동 실행 경로 등록은 없다. 변경 파일은 plan의 A와 공용 패키지 등록 범위다. 실행 시 명시한 세 입력과 sources 목록의 파일을 읽고 새 결과 폴더에만 기록한다.

출력은 learning-links.json, manifest.json, validation.json, review.md, complete.json이다. complete는 묶음 생성 완료이며 의료 검증/공개/학습 완료가 아니다. 새 개념도/포인트의 ID나 수를 과거 후보에 고정하지 않으며 자동 병합/학습 승계도 없다.

## 배포 후 확인·롤백·필요한 사람 승인
운영 배포는 이번 승인 범위에 없으며 수행하지 않았다. 별도 배포 후보와 운영 승인을 만들지 않았다. 로컬 사용 후 입력 불변·completion 출력 해시·실제 시험/제공/해설 구분·미확인 잔여를 확인한다. 실패하면 completion 없는 폴더를 진단 기록으로 유지하고 새 폴더에서 재시도한다.

복원은 새 로컬 도구 사용을 중단하면 된다. 기존 생성/게시/풀이 경로는 그대로 유지된다. 기존 자료나 생성 초안·실패 기록을 삭제하지 않는다. 다음 단계는 새로 구성할 실제 개념도·독립 포인트·문항의 의미 검토 범위를 정해 이 계약으로 전달하는 일이며, 이번 단계 A의 도구 완료로 실제 콘텐츠를 검토/승인한 것으로 간주하지 않는다.
