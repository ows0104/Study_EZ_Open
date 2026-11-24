# Release

## 검사

- `tests/quizbank/test_generate.py`·`test_runtime.py`, `tests/runner/test_root_front.py`·`test_root_front_v3.py`,
  `tests/contracts/test_boundaries.py`: 39 통과, 1 건너뜀.
- 웹 `bank-prompt-current`·`main-quiz-web-author`: 9 통과. `npm run prepare-prompts`로 `web/public/bank-prompt.json` 1.84.
- `quizbank.generate.item_quality_guidance()` 출력에 새 표기 규칙 네 줄이 들어 있음을 확인했다(Main-Quiz 첫 출제·보강·고치기·검토가 붙이는 문단).
- 모델을 돌린 확인은 아직 없다. 다음 새 출제·보강 판에서 답 표기를 강의록과 다시 대조한다(spec의 진단 표와 같은 방법).

## 적용

- 웹 Quiz Bank 출제문: master 병합(=Pages 배포) 뒤 새로 여는 출제부터.
- Main-Quiz: 병합 뒤 러너를 새 커밋으로 다시 설치해야 새 출제·보강·고치기에 들어간다.
- 이미 게시된 문항은 그대로다.
