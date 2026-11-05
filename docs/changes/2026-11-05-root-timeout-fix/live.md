# 시간 초과 공통 수정과 같은 강의 검증

사용자2026-11-05 “시간 초과 원인을 확인해서 공통 파이프라인에서 해결하자. 수정 후 같은 강의로 자동수신된 결과를 재사용해서 학습 화면까지 검증해줘.”

## 원인 분리

원래 두 AUTHOR 호출은 각2400초에 완료되지 않았다. 공통 실행기는 전체 BANK+brief를 단일 최종 JSON으로 재출력하게 했고 부분 실패 스트림은 최종 기록에서 버렸다. 이미 완료한 normalize에는23321 output token의 큰 초기 지도가 있다. 초기 지도를 다시 복사해 반환하는 비용까지 다음 AUTHOR에 중복된다.

짧은 합성 JSON4.82초/15 output tokens, 작은 AUTHOR34.46초/1495tokens, 같은 JSON plain33.68초/1490tokens, 원래 큰 세션의 짧은 답102.9초/15tokens가 실제 완료됐다. 원래 세션의 진단 답 {ok:true}는 출제·의학·학습 결과로 채택하지 않는다. 서비스/스키마 자체의 영구 불능은 재현되지 않았고 큰 AUTHOR 완성 경로가 병목으로 남았다. 공급자 내부의 단일 지연 원인을 확정하지 않는다.

공통 개선은 전체 수용 JSON을 모델이 파일에 작성하고, 불변 초기지도/은행은 로컬 코드로 그대로 복사하며 native 최종 응답은 파일SHA 영수증만 반환하게 하는 방식이다. 실제 합성 모델 확인에서 전체JSON11041bytes, 최종98자,96.6초 완료 및 원래 의미 검증을 통과했다. 실패에는 부분 JSONL/stderr·완료 여부·미상/확인된 사용량을 구분해 보존한다. 원래 수용·원본·정답 검수·상한은 그대로다.

진단 근거는 runs/_development/2026-11-05-root-timeout-fix/probes/{minimal,author,author-plain,same-context}/ 와 native-smoke/다. 첫 diagnostic/smoke 스크립트의 문법 오류는 모델 호출 전에 수정됐다. 공식 참고는 [Structured model outputs](https://developers.openai.com/api/docs/guides/structured-outputs)이며 제약 스키마 지원 사실과 이번 지연 원인 판단은 구별한다.

## 로컬 검증과 실제 적용 전 상태

tmp/rp5 동일 지문의314개 검사 통과: contracts125,runner126,generator22,llm41. 초기 제한 환경의 합성 프로세스 종료1개 실패는 실제 Windows의 동일41검사 통과로 재확인했고 실패도 기록했다. 새 실행기/검사와 실제 로컬 실행기의 관련 파일 SHA를 대조한다.

13:54 KST경 preflight: generation45ba26d191dc468a800360a366c39a55/job544, inputb18eadc7d891aaaa99eda8f3df87215ded7aa38773964c850a8fed6c9509caef, producer61f1b086c18888ca6140f723b98b71619bedcdc4294f5eef2f25b90f6873208c, 원래 세션01a1a972-718c-7192-b882-0b95114bf44b 실행 프로세스0개를 확인했다. frozen packet/수신76문항/82쪽 원본/84개 렌더 파일/완료 normalize/원래 실패와 교정1회 상태 검사를 통과했다.

아직 수정된 방식의 실제 AUTHOR/source/medical/게시/학습은 완료로 세지 않는다. 실제 실행 결과를 아래에 추가한다.

## 같은 자동수신 결과의 실제 후속 실행

수정된 공통 실행으로76문항 AUTHOR를180.799초에 완료했다. 전체 수용 JSON237832bytes는 모델이 로컬 코드로 작성했고 native 최종 응답은98자였다. 원래15목표/22포인트의 text·scope·ID를 유지하고 초기 잘못된 선행 관계를 원본교정1회 안에서 처리했다. producer61f와 원래 packet/webResponse/normalize/두 실패/미상 사용량을 그대로 유지했고 새 native session/adapter SHA/실제 파일·계약·입력·사용량 영수증을 별도 보존했다.

StudyEZ 같은입력 재개 버튼으로 이어 source-0을299.255초, 독립 blind medical-0을83.785초에 완료했다. source는 required_gap19/question_fix4/map_fix1과 별도 limitation2/confirmation2/optional_extension4를 기록했다. 의료 검수는 ok65/doubt8/wrong3이다. 이를 통과나0건으로 바꾸지 않았다. 실제 자극이 필요한5개 방향도 미충족 상태에서 원본 검수의 보완 대상으로 남았다.

정규 repair-1에서 OpenAI가 “limited access to this content for safety reasons”라는 명시적 생물학 콘텐츠 제한으로 거절했다. 출력 파일/완료 응답은 없고 해당 native 호출은 failed다. 현재 총3회 중2회가 소비된 상태이며 이를 초기화하지 않는다. 다른 모델/전송 경로나 자료 변형으로 재호출하지 않는다. 공급자 내부의 과거40분 지연 원인이 이 거절과 동일했다고 단정하지 않는다.

원래 실패 로그는 .native/repair-1/provider-rejection.log로 별도 보존하고 content-block.json을 원장/입력/packet/진단 SHA에 묶었다. 기존 ledger는 바뀌지 않았고 모든 완료 단계의 원본·수용·사용량·file receipt 검사를 다시 통과했다. 실제 공통 CLI 재개 진입점도 MODEL_CONTENT_RESTRICTED를 표시하며 생성기/모델 호출 전에 중단됐다. 추가 오류 분류/증거 변조·동일 입력 재호출·미완료 게시 차단9개를 포함한323개 검사 통과가 최종 지문에 묶인다.

14:28 KST 운영 읽기 확인: received=true,privatePilot=true,published=false,state=failed이며 blockClassification=model_content_restricted다. 기존 콜린성69문항 bank c7fbb80dee4540a1은 ready/public 상태를 그대로 유지한다. 실제 같은 강의의 뿌리 학습 URL도 “아직 공개된 뿌리 학습 범위가 없습니다”를 표시한다. 실제 문항/답/지도 학습까지의 성공을 주장하지 않는다. 화면은 live-learning-held.png다.

공통 사전 차단의 실제 앱 경로도 확인했다. 원래 거절 로그를 별도 보존한 뒤 같은입력 재개를1회 눌렀으며, 생성기/모델 호출 전에 MODEL_CONTENT_RESTRICTED로 종료됐다. root 모델 사용량 기록은8건으로 동일했고 추가 모델 호출은0건이다. 앱도 한국어 콘텐츠 제한·기록 보존 사유를 표시했다. 최종 실제 화면은 live-learning-blocked.png다. 이 확인은 거절된 내용을 공급자에 다시 전송한 재시도가 아니며 수정2회 상태/미게시/학습 미진입을 유지했다.
