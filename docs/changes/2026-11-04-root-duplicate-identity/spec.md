# 자동 시험일과 재개 요청의 동일 작업 보존 — 설계

## 요구사항과 수용 기준
source 요청은 원래 시험일 선택(null 포함)과 확인된 시험일을 구분한다. public_job.input.examDate는 원래 선택을, 관리자 응답 requestId는 원래 ID를 반환한다. 웹의 '같은 입력·남은 횟수로 재개'는 해당 ID/원래 입력을 전송한다. 이전 API와 화면의 requestId 부재는 기존 fallback을 유지한다.

## 책임·입출력 계약·오류 상태
순수 입력 비교는 subject/run/title, 제공 지도/포인트/범위/authoring/inputMode, 확인된 시험일, 고정 원본의 원래 메타데이터를 비교하고 세대별 snapshotKey와 requestedExamDate 차이만 무시한다. 원본/범위/시험일/출제 모드가 달라지면 재사용하지 않는다. 기존 owner/privatePilot 충돌은 계속409다. 기존 digest 조회에 이 동등성 조회를 추가하며 강의 잠금 안에서 수행한다.

이미 등록된 중복의 MD는 기존 generation을 덮어쓰지 않고 해당 중복 row에 실제 원문·파일 지문을 저장한다. 더 오래된 동일 입력 row에 supersededBy로 연결하고 job은 중복 요청 종료(원문 보존)/모델 미등록 상태로 고정한다. latest는 이 원본 generation을 표시해 반복 전송하지 않는다. 취소된 작업의 새 수신 거절, 원문 덮어쓰기 거절, 강의/원본/MD/프롬프트 지문 검증은 유지한다. 기존에 열린 중복은 운영 도구의 정확한 ID와 동등성 확인 뒤 같은 처리로 보존한다.

## 호환성과 데이터 보존
DB 마이그레이션/기존 은행 교체/생성기 runtime 변경/추가 모델 호출이 없다. packet의 중복 연결은 inputHash에 포함하고 순환/다른 강의/다른 owner 연결을 거절한다. 운영 보정은 job525와 두 정확한 generation만 대상으로 하며 모든 증거를 남긴다. 원래 시범의 failed 상태·수정/검수 한도와 미게시 결과는 바꾸지 않는다.
