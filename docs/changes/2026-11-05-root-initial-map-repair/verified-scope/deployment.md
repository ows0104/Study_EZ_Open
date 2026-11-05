# 실제 배포·이어검증 — 2026-11-05 KST

API revision: studyez-api-release-1793844015758744700 / candidate 06fea6c5d6e4547f985c43b7ba7d519ac73e60b9cdd16c3b1bffb36d4607742c / status succeeded / postcheck True. 기존root enabled=true를 실제 revision에서 확인했다. 기존 운영 웹과 DB/은행/학습은 변경하지 않았다.

최종 검증 source bcccdf501ab2694831907ee0d000066d7602b24216eb29572760e3b24f906878 / plan b9b38073e2a0f8d3c5811ea778272073d31d858f7ed3a37e09c91f54bbd8f0a3. 계약125/생성509/러너32, 서버19파일, 실제 로컬브라우저1/typecheck/build 통과.

실제 packet/job: 45ba26d191dc468a800360a366c39a55 / 544. 최초지도 오류는 선행7개의 관계종류 및2개끝점 불일치다. normalize 모델호출16.4분의 완료 응답/사용량과 원래failed 원장을 보존한다.

복구 proof: 0f2826f6e38ecee2286ded5f2adcd98cba4eddee752f808bc92b1e320712dfe2. 원래 identity ecd23d10601d95f94e744da8b65b1838b3b378ce65ff5189764cc974757c7ce7, 현재 identity 61f1b086c18888ca6140f723b98b71619bedcdc4294f5eef2f25b90f6873208c. 실제 실행기와 검증 사본의 새 identity가 일치한다. input/raw/usage/packet/원본2개의 파일SHA 모두 그대로며, 이전failed ledger도 proof에 원형 보존됐다. 복구 명령은 모델/DB 호출을 하지 않았다.

11:03 KST경 StudyEZ 같은입력·남은횟수로재개 버튼으로 같은 작업을 재개했다. 재전송/수동본문수정/콜린성교정/상한초기화 없음. normalize 캐시를 재사용하고 generate 단계가 시작되며 초기지도교정1회를 총3회에서 차감했다. 실제 source/medical/게시/학습까지는 아직 미완료다. 원문 웹 ID 76개는 그대로 유지해야 한다.
