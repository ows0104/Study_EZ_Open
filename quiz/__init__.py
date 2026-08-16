"""복습 퀴즈 → Anki 파이프라인의 코드 절반.

이 패키지 안의 모든 모듈은 LLM을 호출하지 않는다. 의미 판단은 전부 스킬
(.claude/skills/quiz) 쪽 모델 호출이 담당하고, 여기서는 결정론적으로 검증
가능한 것만 다룬다. 이 경계를 흐리지 말 것.
"""

__all__ = ["cloze", "textutil", "render", "notetype"]
