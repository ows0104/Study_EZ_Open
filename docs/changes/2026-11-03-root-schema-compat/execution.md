# 동일 시범의 형식 오류 복구

대상 generation `f0a8f3b68e3642598f85bbf462e1dc55`, job `524`. 실제 웹 문항은 그대로 수신·보존됐으며 다시 전송하지 않았다.

실패 identity `6f3aac4eca8854d9188e1f6890438b0df2ddc5242bdff080b8a50a88b730296f`의 normalize는 내용 생성 이벤트 없이 strict schema HTTP400으로 종료됐다. 현재 원장과 전체 오류 이벤트 순서, 입력 지문, 출력 부재와 수정0회를 검증한 뒤 명시적 유지보수 함수를 한 번 호출했다. 실패 원장은 `preflight-rejection.json`, 원래 오류 로그는 `preflight-rejection.log`로 같은 작업 폴더에 보존했다. proof hash는 `f004a0aeaaa7b47e971cae8204360db08e01a271d665c25c1db0f0bb67c3b95d`다. 기본 실행의 ambiguous/started 실패 차단은 그대로다.

서버 전용 Python에는 PDF 라이브러리가 없어 첫 유지보수 호출은 import 시점에 실패했고 원장에 손대지 않았다. 생성기 환경에서 동일 증거를 검증해 복구한 뒤 서버 환경의 기존 재개 서비스로 같은 job을 queued로 돌렸다. 기존 러너가 이를 받아 현재 `normalize: started`, 원본 기반 지도·포인트 준비 중이다. 아직 최종 대조·독립 정답 검수·게시 완료는 확인되지 않았다. 추가 복구·재시작·코드 변경으로 실행 횟수를 초기화하지 않는다.

최신 시범 상태와 69문항 보존 검사는 `../2026-11-03-root-one-click/pilot-status.json`을 본다. 검증 정본은 `tmp/root-web/docs/changes/2026-11-03-root-schema-compat/state.json`이다. API/웹은 앞선 배포를 유지하며 이번에는 로컬 생성기만 수정했다.
