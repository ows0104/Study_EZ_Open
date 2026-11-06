# Main Quiz 실제 운영 반영

- PR8 병합: 7b96003fce476157d909863d64389d7b2f9a00b0. 직전4초에 병합된 UI 개편 PR9를 포함한 최종 master다. 이 세션은 다른 UI 소스를 수정하지 않았다.
- PR 검사42168352945 성공, master 검사/배포42170683304 성공. master Python1978+12+2=1992통과·1skip, 서버112모듈 성공·웹 타입/빌드·브리지/게이트·고정 서버 후보 성공.
- API: studyez-api-release-421706833041, 100% 전환 및 health의 정확한 SHA·보호 경로401 성공. 이전은 studyez-api-release-420497606571. 영수증은 production-api-receipt.json.
- Pages: 5c2b062e-241d-47a9-8c03-914a489d394d, https://5c2b062e.study-ez-open.pages.dev. deploy success 2026-11-06 06:16:51 UTC = 한국15:16:51. 같은 SHA임을 확인했다.
- 실제 공개 assets14개를 import 경로로 추적해 Main Quiz entry·화면·선택 입력·3등급·추가 저작 지침을 확인했다. 최초 검사는 Python 기본 헤더403 및 분리된 useMainQuizEntry chunk로 실패했으며, 정상 웹 헤더와 실제 import graph 대조로 사후 검사 성공했다. 공통 프롬프트1.82 유지. 기본 도메인 studyez.kr와 pages.dev 모두200. production-web-postcheck.json 참조.
- 두 병합이4초 차이로 발생했고 이전86da Pages 빌드가 앞에 있어 최신7b 웹이 대기했다. 1회 retry는304로 새 게시를 만들지 않았다. 관리 UI는 로그인 필요로 변경하지 않았다. 직접 게시 경로는 별도 브랜치에서 기록만 준비했으며 자동 배포가 완료되어 산출물 생성/업로드 전에 종료했다. 직접 게시나 보안/빌드 설정 변경은0회다.
- 최종 master를 별도 localhost5199/격리 DB에서 다시 열어 흰 UI와 Main Quiz 조합·표·390px 문서375px을 확인했다. screenshots는 시각화 폴더 main-quiz-merged.jpg 및 main-quiz-merged-mobile.jpg. 원래 E2E/풀이/문항/검수/실패/상한은 보존했다. 운영 학습/문항/DB 쓰기·모델 호출 없음.

현재 사이트: https://studyez.kr. 기존 자료는 호환 화면과 기록으로 보존하며 새 검토·허용 자료가 준비된 강의에서는 같은 Main Quiz 진입이 새 흐름을 연다. 로컬 러너 설치/재시작이나 기존 강의 일괄 전환은 이 배포에 포함하지 않았다.
