# 회상 단위별 문항 설계·검수·분산 충족과 Main Quiz 비교 — 배포 준비

## 코드 리뷰·검증 결과
추가 지시 extract/author/source를 승인 문안에 맞춰 수정했다. 공통 bankPrompt1.82 파일은 바이트 동일하게 보존한다. opt-in recall-units/1에서만 명시 단위별 cue/answer_scope/components/관계를 투영해 실제 문항을 검증한다. 모든 단위를 확인해야 부모 내용 충족이며 별도 종합 방향은 한 문항 전체 회상을 계속 요구한다. design_checks가 모든 문항에 있어야 하고 wrong/doubt는 채택되지 않는다. 내용 충족과 의학/선행 검수를 반영한 goalPreparation을 별도로 집계·재검증한다. 구형 /2와 실제 raw 판정/원문을 유지한다. 과거 파생 coverage.reason 구절 순서만 같은 경우에는 구절/중복 개수를 보존하여 호환 검증한다.

최종 source hash 0b472b6889614aba3b2da34075b19a749128848701ca2a869ecdeaf10441180d. 계약/생성 회귀254개, 별도 회상·파이프라인 검사25개(회귀와 일부 중복), 격리 서버 root_generation/root_pipeline_v2/root_preservation/root_recall_units, 실제 Main Quiz 표·빈칸 회귀4개 및 웹/비교화면 TypeScript 검사를 통과했다. 표 앞뒤 빈칸 번호가 초기 구현에서 뒤쪽1로 재시작되는 문제를 테스트로 찾아 offset을 유지하도록 고쳤다. 초기 pure validator가 dynamic JSON Schema의 type 없는 enum 노드를 읽던 오류도 static 구조검증과 명시 ID검증으로 수정했다. 실패와 이후 통과를 구별한다.

UI 파일은 generation 영역 지문에 포함되지 않으므로 ui-checks.json에 실제 BankStem/test/compare.tsx/css 해시를 별도로 저장하고 live-comparison에서 재대조한다. 브라우저에서 기존 Main Quiz QuestionBody/AnswerBody 재사용, 세 범위의 이전/이후 전환, 빈 표의1~4번, 답 공개 후 셀별 정답, 정답 의심 배지/검수 기록 펼침을 확인했다. 비교 화면에는 뿌리 학습 명칭을 사용하지 않는다. 실제 캡처는 시각화 폴더 recall-comparison.jpg, 탭은 deliverable로 유지했다.

## 배포 대상 버전·순서·데이터 변경
별도 codex/recall-units 로컬 후보다. 기존 강의·원본 세 문항·result/ledger와 실제 풀이 SQLite는 읽기만 하며 새 질문은 RU 접두 ID로 분리한다. 부모 목표는 D012/D019/D032이고 새 문항은4/1/3개(총8), 모델 저작1회·별도 원본/설계1회·독립 의학 검수1회다. 이전 강의의3회 소비를 재시작하지 않고 별도 trial-ledger에 새 승인 범위/호출을 기록했다. 원본 PDF2개와 관련 물리쪽 PNG12개만 실제 비교 검수에 사용했으며 강의 전체 재검수로 표시하지 않는다.

실제 저작 완료 파일은 T008/T015의 파생 target.relation_ids에 새 directions에서 제거한4개 관계 ID가 남아 있어 최초 host 수용이 실패했다. 원본 파일·Native 완료 영수증·실패 이유를 보존하고, 명시 accept-references에서 해당 두 목록을 현재 directions의 실제 관계 합집합으로만 정렬·정합화했다. 질문/답/채점/의학 충돌은 raw와 정확히 동일하며 별도 projection 증명에 전후 해시와 변경 목록·모델0회를 기록했다. 이 수정을 의학 검수로 대신하지 않고 이후 두 독립 검수를 실제 수행했다.

원본/설계는8문항 모두 ok, 독립 의학은7 ok/1 doubt/0 wrong. RU012A는 '급성 CNS 감염'의 감염 유형·연령 조건이 넓다는 의견을 보존하고 준비 과제에서 제외했다. 내용상3목표 확인과 별도로 준비 판정은 병원체 목표 partial(3/4단위), 증상 ready(1/1), CSF ready(3/3)다. 비교 화면에는8초안을 보여 주되 의심 문항을 표시하고 원문 검수 의견을 답 뒤에서 읽을 수 있게 했다. 미해결0이나8문항 학습준비를 주장하지 않는다.

## 배포 후 확인·롤백·필요한 사람 승인
운영 배포·공용 은행 교체·권한/DB 변경은 없다. loopback 127.0.0.1:5197/compare.html의 별도 로컬 Vite 화면과 JSON ZIP을 제공한다. 정상 API를 재연결하거나 원래 학습 기록을 새 ID에 승계하지 않는다. 이전 기본 원본 프롬프트 변경도 없다. 사용자 현재 구현·재생성 비교 승인을 적용했고 같은 허락을 다시 요청하지 않았다.

최초 비교 화면의 Vite 플러그인 import 오류는 종료된 소유 프로세스만 확인해 기존 web/vite.config를 재사용하도록 고쳤다. UI 프로세스 소유권과 실패 로그도 새 실험 폴더에 보존한다. 복원은 이 실험의 소유 프로세스만 종료하고 별도 코드 후보를 사용하지 않는 것으로 충분하다. 기존 PDF/실패/원문/풀이 이력은 지우지 않는다. 다음 수정은 사용자 비교 피드백을 바탕으로 별도 범위에서 진행한다.
