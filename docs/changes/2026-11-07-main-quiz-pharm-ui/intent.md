# Main-Quiz 약리 블럭 UI 복원

## 문제와 사용자 효과
사용자 2026-11-07: “Main-Quiz UI를 이전 약리 블럭때의 UI로 해줘.” 참고 슬라이드 누락, 불필요한 버튼, 불필요한 답 입력, Space 후 3번 평가 비활성화, 개념지도를 원하는 이유를 직접 밝혔다.
후속 선택: “이전처럼 4개 평가 버튼”. Again·Hard·Good·Easy를 사용하는 이전 약리 Quiz Bank의 풀이 구성을 새 자료에도 복원한다.

## 범위와 성공 기준
문제 → Space/답 보기 → 답·해설·참고 슬라이드 → 1~4 평가의 흐름을 복원한다. 직접 답을 적는 입력창을 없애고 부가 기능은 접는다. 개념은 관계가 보이는 그래프로 표시한다. 문항/출제/검수/학습 이력을 보존한다.

## 근거·미정 사항
최신 origin/master a4625641에서 codex/main-quiz-pharm-ui와 전용 worktree를 만들고 dashboard를 pull/확인/등록/push했다. 기존 작업표의 추출 프롬프트, 실험 전용 저장소, 강의 패널 예정 작업과 소스 수정 범위는 겹치지 않는다.
이전 구성의 기준은 BankSolve.tsx의 quiz-progress·quiz-card·quiz-bar, 네 단계 평가와 ConceptMap.tsx다. 새 Main Quiz는 BankStudy.tsx에서 RootLearningPage로 분기한다.
구체적인 spec/plan을 작성한 상태다. 구현 승인 및 테스트/배포 근거는 아직 없으며 승인 기록을 만들지 않는다.
