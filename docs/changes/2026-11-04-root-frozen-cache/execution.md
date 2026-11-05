# 보관본을 사용해 같은 작업 재개

source-1의 동일 세션 계속 실행은 실제 모델 AUDIT 출력으로 완료됐고, 원장과 usage를 보존한 채 기존 대기열에 돌아갔다. 이후 정상 러너가 고정 PDF를 다시 다운로드하다 response.read에서 ConnectionResetError로 모델 호출 전에 중단됐다. 완료 source-1은 손상되지 않았다.

지문이 맞는 보관본의 네트워크 없는 재사용, 불일치 보류, 최초 다운로드의 일시 오류 최대3회와 atomic 저장을 구현·검증했다. 생성기 자체와 runtime identity `f365489f12a67b98760e45aaa5cf3139b365a3d488a4662fc8d81abda33258c7`은 바꾸지 않았다. 계약/검수 판정이나 수정 상한도 바꾸지 않았다.

러너 514개 회귀와 관련 13개 테스트 통과/release gate 확인 후 같은 generation `f0a8f3b68e3642598f85bbf462e1dc55` / job `524`만 기존 resume 서비스로 재개했다. 기존 source-1과 앞선 모델 단계는 다시 호출하지 않았다. medical-1이 실제 완료됐고 현재 repair-2가 시작돼 수정2/3회 소비 상태다.

source-1은 원본 대조 기준 ok117/doubt8, 포인트 covered10/partial13/excluded3을 반환했다. 연결 기록의 tested/provided/explanation disjoint 형식 오류와 기존 BANK 구조/출처 지적은 수정 입력으로 보존했다. 이 수치와 단계 완료는 최종 게시나 의학 검수 통과를 의미하지 않는다.

기존 69문항과 bank/validation/review 지문이 그대로이고 RootControl/신규 게시 결과는 없는 것을 확인했다. 정본 검증은 `tmp/root-web/docs/changes/2026-11-04-root-frozen-cache/state.json`이다.

2026-11-04 10:32 KST 관측: repair-2는 88문항으로 완료됐고 전체 BANK 검증과 구조 검증이 모두 pass, 오류0/경고34였다. source-2와 medical-2도 실제 완료됐다. source-2는 ok78/wrong1/doubt9, 포인트 covered7/partial16/excluded3을 반환했고 연결 기록의 empty relation assignment 오류를 남겼다. 해당 내용 지적과 계약 오류를 최종 repair-3 입력에 함께 보존했다. 현재 repair-3 started, 수정3/3회 소비 상태이며 result/published는 없다. 최종 source-3/medical-3과 실제 게시 여부를 기다리고 있다. 추가 수정이나 검수 상한 초기화는 하지 않는다.

최종 결과: repair-3/source-3/medical-3 모두 실제 완료됐고 13개 단계 파일 지문이 원장과 일치한다. 88문항의 BANK 구조 검증은 pass다. 원본 판정 ok80/doubt8, 독립 정답 판정 ok87/doubt1을 보존했다. 원본 AUDIT의 방향별 tested 관계 배정이 계약에 맞지 않아 `mapping tested relations: unknown references ['R18']`로 최종 조립이 중단됐고 result/published는 없다. R18은 전역 관계에는 있으나 해당 방향의 관계 집합에 속하지 않는 배정이다. 별도 진단에서 방향 밖 배정2행을 확인했고, 두 행만 빼는 것으로 모든 coverage 검증이 해결되지 않는 것도 확인했다. 원문이나 판정을 직접 고치지 않았다. 운영 job524는 failed, RootControl은 없고 기존69문항/검수/지문은 모두 보존됐다. 상세 증거는 `../2026-11-03-root-one-click/pilot-final-check.json` 및 pilot-status.json이다.
