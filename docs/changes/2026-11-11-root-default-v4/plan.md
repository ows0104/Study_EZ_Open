# Main-Quiz 관리자 출제 기본값을 새 구조 2로 — 구현 계획

## 변경 범위·대상 파일·순서
1. `web/src/bank/RootGenerationPanel.tsx`
   - `DEFAULT_MODE='map-tree-v4'`를 추가한다.
   - 초기 상태, `modeOf`의 기본 분기, 지도 사용 체크 해제 시 돌아갈 값을 모두 `DEFAULT_MODE`로 맞춘다.
   - 라디오 순서와 라벨을 바꾼다.
2. `web/tests/main-quiz-generation-button.test.cjs`
   - 기본 클릭이 map-tree/3을 보내는지 확인한다.
   - map-tree/1을 여전히 고를 수 있는지 확인한다.
   - 지도 사용 체크를 해제하면 기본으로 돌아가는지 확인한다.
   - 바뀐 라디오 순서에 맞게 인덱스를 고친다.

## 검사 명령과 성공 조건
- `node --test web/tests/main-quiz-generation-button.test.cjs`: 전부 통과
- `npm --prefix web run typecheck`, `npm --prefix web run build`: 통과 (CI의 Web typecheck and build와 같은 검사)

## 위험·복원·승인할 범위
- 승인 근거: 사용자 요청 원문 「관리자 출제 기본값을 새 구조 2로 바꾸자.」(2026-11-11 채팅)
- 화면 기본 선택만 바꾸므로 DB·운영 데이터·생성기는 바뀌지 않는다.
- 이 변경만으로는 출제가 일어나지 않는다. 출제는 관리자가 강의마다 버튼을 눌러야 하고, 그 클릭이 그 강의의 자료 전송·공개 승인이다(2026-11-09 결정).
- 되돌릴 때는 커밋을 revert한다. 웹은 Pages 재배포로 복원된다.
