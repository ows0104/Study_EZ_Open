# Codex 기본 모델 gpt-6.2-sol

## 문제와 사용자 효과
사용자 2026-11-24: 「현재 CLI는 어떤 모델을 써? 6.2가 새로 출시되었다고 해서.」 → 「어 고치고 병합후 재설치해줘.」

러너의 모든 Codex 호출(Main-Quiz 앞 단계·/4 출제·검수·선지, 예습·복습 덱 quizgen, 재현 채점)은
`studyez_llm/codex.py`의 `DEFAULT_MODEL = "gpt-6.1-sol"`을 쓴다(러너 PC에 `STUDYEZ_MODEL` 없음).
Codex 모델 목록(2026-11-24 17:09 받음)에 `gpt-6.2-sol`·`gpt-6.2-astra`가 있다.

## 범위와 성공 기준
- 기본 모델과 채점 모델을 `gpt-6.2-sol`로. `--model`·`STUDYEZ_MODEL`·`runs/model-overrides.json`은 그대로 우선한다.
- 도움말 문구·docs/quizgen.md·docs/pipeline.md의 모델 이름을 맞춘다.
- 성공 기준: 러너 CLI(0.167.0-alpha.3.2)로 6.2 호출이 된다. 검사 회귀 없음. 재설치한 러너가 새 기본값을 읽는다.
- 넣지 않는 것: 추론 강도(`~/.codex/config.toml`의 `high`), 단계·지시문·묶음 크기, 서버·웹·DB.

## 근거·미정 사항
- 2026-11-24 러너 래퍼(`codex.run`, 공급자 studyez)로 `gpt-6.2-sol` 짧은 호출: 6.1초, 정상 응답.
- 미정: 6.2의 출력 속도·토큰 수와 출제 품질. 오늘 맞춘 300초 선(900초로 올림)·선지 묶음 12문항은 다음 출제의 기록으로 본다.
