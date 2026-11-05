# 같은 검수 세션 계속 실행

대상은 승인된 콜린성(1) generation `f0a8f3b68e3642598f85bbf462e1dc55`, job `524`다. 2026-11-04 확인 시 source-1은 started만 남았고, 정상 재개는 기존 안전 규칙으로 failed 처리됐다. 뿌리 콘텐츠와 RootControl은 게시되지 않았다.

해당 CLI 세션 `01a1a17d-8ae3-79b1-94a3-1b1b4900c67f`에는 최종 응답/완료/오류/중단 이벤트가 없고 원래 작업 폴더가 남아 있었다. 원래 시작 시각의 CLI 프로세스는 없었다. 모델은 같은 `gpt-6.1-sol`, material 37개가 프로젝트 보존본과 일치하고 원래 프롬프트 전체·context·BANK/brief·문항/원본 지문이 일치함을 검사했다. Windows CRLF만 LF로 정규화해 비교했다.

계약 72, 러너 전체 508개 검사 및 release gate 통과 후, 실행 슬롯과 같은 강의의 다른 열린 bank 작업이 없고 기존 작업이 failed/취소 아님을 재확인했다. job524만 `root-session-524` worker로 점유했으며 다른 작업은 건드리지 않았다. 드라이버 PID는 시작 시 `53692`다.

동일 source-1 세션에 한 번의 명시적 `exec resume`을 사용한다. 새 독립 검수나 웹 출제, 완료 지도/정리 재생성, 수정/검수 횟수 초기화는 하지 않는다. 부분 사용량은 알려진 값과 불명확 부분을 구분해 보존한다. 원래 세션은 `source-1-before-continuation.jsonl`, 증거와 상태는 `source-1-continuation.json`, 반환 모델 응답은 `source-1-continuation-response.json`에 보존한다. 실패/중단 시 같은 도구를 자동으로 다시 호출할 수 없다. 취소·중지·heartbeat는 기존 Agent 경로를 따른다.

동일 세션의 실제 AUDIT 출력이 완료됐고 source-1 캐시와 continuation journal은 completed다. 기존 대기열에 돌아간 뒤 medical-1도 완료됐다. 수정1회 소비와 모든 완료/실패 증거는 그대로 유지했다. source-1의 연결 기록 역할 중복(disjoint) 오류와 repair1의 구조/출처 오류·문항 증감 기록은 후속 수정 입력으로 보존했으며, 이 복구 도구는 그 판정을 통과로 바꾸지 않았다.

정본 검증·리뷰: `tmp/root-web/docs/changes/2026-11-04-root-session-continuation/state.json`.
