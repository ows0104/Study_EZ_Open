# Release

## 검사

- `web/tests/answer-readable.test.cjs`·`answerPoints.test.cjs`: OX 기대값을 「X: 이유」로 바꾸고 새 검사 하나
  (이유가 explanation·옛 채점 단위일 때, 이유 없음, 내 답). 모두 통과.
- `bank-prompt-current`·`main-quiz-web-author`: 통과. `npm run prepare-prompts`로 `web/public/bank-prompt.json` 1.83.
- 웹 전체 `node --test tests/*.test.cjs`: 실패 26건(53줄)은 origin/master에서도 똑같다. 메인 체크아웃의
  node_modules에 playwright·pdfjs-dist가 없어서다. 이 변경이 더한 실패는 없다.
- `tests/quizbank/test_generate.py`·`test_runtime.py`: 16 통과.
- 브라우저: `web/tests/bank-ox-answer.html` 고정물(콜레라 실제 문장 + 참 명제 예 + 옛 은행)에서
  정답 줄이 「X: …」「O: …」로 보이고 해설 칸이 없으며, 이유는 본문 굵기·O/X와 감별어만 파란 굵게다.

## 적용

- 웹 표시는 master 병합(=Pages 배포)으로 공개된 모든 은행에 적용된다.
- 프롬프트는 새 출제부터. Main-Quiz는 러너 재설치 뒤 새 출제부터 v4 add/fix가 바뀐다.
- 이미 공개된 X 쏠림 문항은 그대로다.
