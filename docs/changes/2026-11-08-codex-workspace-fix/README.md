# 예습 덱 must_know.json 미생성 — Codex 쓰기 범위

## Intent

2026-11-08 밤 예약 빌드에서 2026-11-09 예습 4편이 ① 단계에서 멈췄다.

| 편 | 작년 짝 | 로그 |
|---|---|---|
| 261109_01 미생물학) 헤모필루스, 보르데텔라, 나이세리아 | 251112_01 | runs/251112_01/prequiz.log |
| 261109_02 미생물학) 레지오넬라, 리스테리아, 바실루스 | 251106_05 | runs/251106_05/prequiz.log |
| 261109_03 약리학) 항생제 약리학의 기본 원리: 항생제 내성 | 251110_03 | runs/251110_03/prequiz.log |
| 261109_05 감염학) 항생제 내성균의 진단과 치료 | 251110_05 | runs/251110_05/prequiz.log |

모델은 JSON을 만들고 검증까지 했다고 답했지만 "지정 경로는 쓰기 허용 범위 밖"이라며
작업폴더에 저장했다.

## 원인

- 11-07부터 러너는 `.runtime/main-quiz-6da5a7f42bfb/` 설치본에서 돈다(`launch-runner.pyw`).
- `quizgen/runbase.py`의 `agent()`가 `cwd=Path.cwd()`(= 설치 폴더)로 Codex를 띄웠다.
  `workspace-write` 샌드박스는 cwd 하위에만 쓰게 한다.
- 설치 폴더의 `runs`는 진짜 `runs/`를 가리키는 링크라 샌드박스 범위 밖이다.
  저장소 루트에서 돌던 때는 `runs/`가 cwd 하위라 문제가 드러나지 않았다.
- 네 편이 모두 `.runtime/.../must_know.json` 하나에 덮어썼다. 남은 것은 마지막(251110_05)뿐.
  쪽 이미지 `tmp_pdf_*` 등 약 100MB도 설치 폴더에 쌓였다.

## Spec · 변경

- `runbase.agent()`: cwd를 이 편의 출력 폴더(`self.out`)로 둔다. 러너가 어디서 돌든 같다.
- 쪽 이미지는 `%TEMP%/studyez-pages/<출력 폴더 해시>`에 그리고, 세션이 끝나면 지운다.
  runs/에 100MB씩 남기지 않기 위해서다.
- `session.run_agent(scratch=)`: 어댑터 문구에 이미지 폴더 경로를 넣고 `writable`로 넘긴다.
- `codex.command(writable=)`: 저작 세션에만 `--add-dir`. 가림 세션은 그대로 read-only.
- 프롬프트 본문·검증·출제 정책은 바꾸지 않았다. 모든 입력·출력 경로는 이미 절대 경로다.

## Test

- 새 검사 3개: 수정 전 코드에서 3개 모두 실패, 수정 후 통과.
- `pytest tests/quizgen tests/studyez_llm`: 570 통과.
- 실제 Codex(빈 폴더 둘): cwd 출력 폴더와 `--add-dir` 이미지 폴더 양쪽에 쓰기 성공.

## 남은 것 (이 PR 밖)

- `.runtime` 설치본은 이 코드로 다시 설치해야 반영된다. 그 전 예약 빌드는 같은 이유로 실패한다.
- 네 편은 재실행해야 한다. 앞 세 편의 must_know.json은 덮어써져 없다.
- 261102_03 감염병의 진단 Quiz Bank는 OpenAI 콘텐츠 제한 거절(`MODEL_CONTENT_RESTRICTED`)로 별개 문제다.
