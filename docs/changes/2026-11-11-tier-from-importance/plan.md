# Plan

1. 브랜치 `claude/tier-from-importance`(origin/master b2e94419), 대시보드 등록.
2. R1·R2: studyez_contracts/roots/generation_v3.py.
3. R3: quizbank/connection_generate_v3.py, quizbank/connection_generate_v4.py(호출 두 곳).
4. R4: content/prompts/learning-links/v3·v4/add.md·fix.md.
5. 검사: tests/contracts/test_tier_from_importance.py(새), tests/runner/test_root_native_v3.py(모델 출력 고정물에서 tier 제거).
6. 회귀, Draft PR. 병합(=배포)·러너 재설치·실제 재생은 별도 승인.
