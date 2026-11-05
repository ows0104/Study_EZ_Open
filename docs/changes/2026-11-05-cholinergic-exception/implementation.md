# 구현·실행 경계

- 사용자 승인: 93문항 기준 지정 핵심 보완 추가 1회, 같은 PDF 35쪽·족보, 같은 OpenAI Codex 내용 모델, 운영 미게시. 최초 실행의 3회와 앞선 예시 후속 3회는 별도 불변 이력이다. 이번 후속 계보는 4번째이며 전체 기록을 초기화한 것이 아니다.
- 새 출력: `runs/_examples/cholinergic-exception-20261105`. 이전 `cholinergic-findings-20261104` 결과/ledger/화면과 원본 실행은 덮어쓰지 않는다.
- `exception.py`는 기존 once-only CLI·delta 재생·실제 PDF crop·도구 없는 medical 함수를 재사용한다. repair/source/medical/resolve 각 1회 제한이며 실패도 소비한다. 실제 clinical 교정은 Q066/Q077/Q092/Q101/Q109/Q130/Q142 7개, 93문항 유지. Q066/Q130은 prerequisites만 변경했다. 독립 재검수의 완료는 clinical 전 항목 무조건 해결을 의미하지 않는다.
- `resolve_compact.py`는 동일 최종 단계의 원래 목표 정의·이슈·요약을 보존하고 중복된 옛 은행/검수 표만 생략한다. 실제 입력과 스크립트 hash가 단계에 보존된다. 추가 내용 교정이 아니다.

## R35 검토 상태 집계 복구

교정 모델은 재정의된 R35를 `unreviewed`로 반환했다. 별도 source-4는 Q077 `ok`, R35 `tested`/D10, D10 `reviewed`를 실제로 반환했다. 계약은 미검토 관계의 시험 연결을 거절하므로 원본 응답은 완료됐지만 컴파일이 중단됐다. 원본/모델 출력/판정은 수정하지 않았다.

`assemble.py source`는 위 세 가지 독립 모델 판정과 D10의 단일 R35 연결을 정확히 요구한 뒤, **R35.review_status만** 검수 완료 상태로 반영한다. 임상 condition/근거/목표/문항/판정 payload는 바뀌지 않는다. `brief-before-review-adoption.json`, `assessment-before-review-adoption.json`, `source-review-adoption.json`에 기존 binding과 전후 hash·실제 판정 문구·도구 hash를 보존한다. 검수 완료 brief에 대한 envelope만 다시 계산하며 추가 모델 호출은 0이다. 최종 verifier는 원래 입력 brief와 검수 후 brief의 유일한 차이를 재검증한다. 이 상태는 원본 검토 완료를 뜻하며 임상 안전·운영 승인으로 전이하지 않는다.

## 독립 검수와 표시

source-4에는 과거 sourceAudit/medical 결과 객체를 추가하지 않고 현재 자료/지도/은행/그림을 전달했다. 기존 BANK의 역사적 출처 충돌·해설은 유지한다. medical-4는 기존 `review_prompt`의 문제/정답/해설/출처 충돌 필드와 실제 최종 crop 10장을 보며, 별도 ephemeral 세션의 도구·MCP·기억을 차단한다. 원본 PDF 전체나 새 sourceAudit 객체는 medical 세션에 전달하지 않는다. 기존 출처 충돌에는 과거 검수 언급이 남아 있으므로 모든 역사적 판단 문구가 숨겨졌다고 주장하지 않는다.

최종 의미 검토는 별도 CLI가 원래 20개·3방향·이번 6개 보완 항목과 전체 57방향을 판정한다. 화면의 준비 수는 canonical whole-direction task, 최종 의미 승인, 해당 문항의 source ok와 medical ok를 모두 요구한다. raw source 및 medical 판정은 보존한다. 이전 정의와 다른 D10 및 D15 대체 목표는 숙련도 승계를 가정하지 않는다.

## 검사

공용 계약/생성기 합성 검사 145개 통과. 최초 제한 환경의 4개 실패는 임시 폴더 정리 권한 오류였으며 실제 assertion 실패가 아니었다. 정상 Windows 환경에서 같은 전체 검사를 재실행해 145개 통과했고 두 로그를 보존했다. 별도 artifact/preview 검사는 최종 결과 작성 후 기록한다. 운영 DB·게시·배포·학습 기록 쓰기와 ChatGPT 직접 접속은 없다.
