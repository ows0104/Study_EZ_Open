# 퀴즈 전체 화면 버튼 — 설계

## 요구사항과 수용 기준
1. `StudyNav` 오른쪽(피드백 버튼 앞)에 버튼 하나. 평소 `전체 화면`, 전체 화면 중 `전체 화면 끝`.
2. 클릭 → `document.documentElement.requestFullscreen()`. 문서 전체를 올리므로 이동 줄·다이얼로그·
   플로팅 노트 등 같은 페이지의 요소는 그대로 보인다.
3. 다시 클릭 → `document.exitFullscreen()`. Esc·F11 등 브라우저 방식의 해제도 `fullscreenchange`로 반영한다.
4. `StudyNav`가 사라질 때(학습 화면 이탈) 이 버튼이 켠 전체 화면이면 해제한다.
   학습 화면끼리 이동할 때는 `StudyNav`가 그대로 있으므로 유지된다.
5. `document.fullscreenEnabled`가 false면 버튼을 그리지 않는다.
6. 설명 문구·안내 문장을 추가하지 않는다. 단축키를 추가하지 않는다(풀이 화면의 숫자·V·Z 키와 충돌 방지).

## 책임·입출력 계약·오류 상태
- 새 컴포넌트 `web/src/FullscreenButton.tsx`: 상태는 `document.fullscreenElement`에서만 읽는다.
- `requestFullscreen` 거절(권한·iframe 등)은 조용히 무시한다. 버튼 상태는 실제 상태를 따르므로 어긋나지 않는다.
- 서버 API·DB·이용현황 기록 없음. 브라우저 표시 방식만 바꾸며 학습 기록과 무관하다.

## 호환성과 데이터 보존
웹만 바뀐다. 서버·러너·DB·문항·학습 기록 변경 없음. 이전 서버와 호환.
버튼·화면 이름 변경이 아니고 단축키가 없으므로 `GuidePage.tsx`는 고치지 않는다.
