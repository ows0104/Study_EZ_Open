# 구현 계획
현재 사용자의 “이 6가지를 공통 파이프라인에 반영…구현하고 검증해줘”가 아래 범위의 구현 승인이다. 같은 승인을 재요청하지 않는다.

- 공용 contracts: optional direction 구성요소/시각 요구, question 그림 계약, source-assessment/2와 최신 brief/authoring 계약, 구조화 지적/수정 판정, 완료 검증, 선행 그래프 및 준비 과제 계산. /1의 기존 동작 유지.
- quizbank: 기존 connection_generate 진입점에서 새 요청을 v2 실행기로 연결한다. 초기 지도·생성·최대3수정·원본/독립 검수의 입력/원문/사용량/출력 hash를 보존하고 중단 호출 자동 재실행 금지. 새 프롬프트, 모델 그림 렌더러, 임상 입력 분리. 원문 내용은 모델만 작성한다.
- studyez_llm/session: 실제 이미지를 도구 없는 Codex 호출에 첨부하는 일반 옵션. 경로/이미지 hash를 실행 지문에 포함.
- server/runner: 신규 요청 버전과 결과 검증 연결, 그림이 있는 질문의 안전한 표시, 문항 선행 관계의 추천 순서 반영. 기존 생성/운영 데이터는 변경하지 않는다.
- web: 질문 그림의 공통 표시와 답 숨김 유지. 관리자 기록은 새 지적·미준비 사유를 보존한다.
- 검사: contracts(legacy+신규 의미 계약), generator(합성 원본·다른 강의 ID·그림·수정 라우팅·상한·재개/변조), runner(합성 하위 프로세스), server(격리 DB 요청→게시→질문/답·준비/선행·보존), web(typecheck/build와 실제 브라우저 그림·답 숨김). meaningful regression만 추가하며 실제 강의 모델 호출은 하지 않는다.
- 리뷰/출시: 검사 완료 후 release.md 및 revision-bound 증거를 기록한다. 로컬 구현 완료이며 운영 배포 없음. 복원은 새 코드 미배포/이전 배포 후보 유지이며 기존 자료 덮어쓰기가 없다.

검사 명령은 scripts/check_root_pipeline.py contracts/generator/runner/server/web이다. 검사 도우미 자체도 공통 source fingerprint에 포함한다. evidence area=contracts를 사용하여 서버·웹까지 검증 지문에 포함한다. web 검사는 직접 소유한 임시 로컬 서버/합성 하위 프로세스를 시작·정리하며 실제 ChatGPT는 열지 않는다. 검사 중 발견된 재개 시각 지문·완료 결과 재사용·결합 선행 순환·그림 미확인 클라이언트·임상 문구의 과거 검수 표식도 같은 6종 수용 기준 안에서 검증한다. 기존 입력은 프로토콜 업그레이드만으로 새 작업/수정 예산을 만들지 않는다.
