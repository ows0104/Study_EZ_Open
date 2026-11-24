# Codex 기본 모델 gpt-6.2-sol — 설계

## 요구사항과 수용 기준
R1. `studyez_llm.codex.DEFAULT_MODEL`(따라서 `JUDGE_MODEL`)은 `gpt-6.2-sol`이다.
R2. 우선순위는 그대로: 호출 인자 `model` → `STUDYEZ_MODEL` → 기본값. Main-Quiz 요청별 지정(`runs/model-overrides.json`)도 그대로.

수용 기준
- 인자·환경변수 없이 `codex.model_name()`이 `gpt-6.2-sol`을 낸다(검사).
- 러너 CLI로 `gpt-6.2-sol` 호출이 정상 응답한다(실제 호출).

## 책임·입출력 계약·오류 상태
- 단계 입력·지시문·스키마·상한·결과 계약은 그대로다. 단계 기록의 `model` 칸이 새 이름이 된다.
- 모델 이름은 단계 재개 지문에 들어간다. 재설치 전에 시작한 실행은 원래도 코드 지문이 달라 `--resume`이 필요하다.

## 호환성과 데이터 보존
- 게시된 판·문항·학습 기록·asset을 건드리지 않는다. 새로 시작하는 실행부터 적용된다.
- 6.2가 막히거나 품질이 나쁘면 `STUDYEZ_MODEL=gpt-6.1-sol`로 러너만 되돌릴 수 있다(코드 revert 없이).
