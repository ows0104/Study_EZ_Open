# Main-Quiz /4 고치기는 같은 물음 안에서만 — 구현 계획

## 변경 범위·대상 파일·순서

1. `content/prompts/learning-links/v4/fix.md`: 첫 목록 「지적과 무관한 칸은 바꾸지 않는다」 뒤에 R1
2. `content/prompts/learning-links/v4/item-review.md`: `note`/`fix` 줄 아래에 R2
3. `content/prompts/learning-links/v4/PROVENANCE.md`: 바뀐 곳 기록
4. `quizbank/CLAUDE.md`: 한 문단
5. 새 `tests/quizbank/test_fix_same_question.py`: 문장 고정 5개

PR #238(Draft)과 같은 파일을 건드린다. #238은 사용자 결정으로 이 PR로 대체되고, 그 세션은 보관했다.

## 검사 명령과 성공 조건

```powershell
C:/Users/ows01/anaconda3/python.exe -m pytest tests/quizbank/test_fix_same_question.py -q -p no:cacheprovider
python scripts/development.py verify 2026-11-23-fix-same-question --check regression -- C:/Users/ows01/anaconda3/python.exe -m pytest tests studyez_contracts -q -p no:cacheprovider
```

새 검사 5개가 통과하고, master 지시문으로 돌리면 실패해야 한다.
전체 검사는 이 변경과 무관한 기존 실패만 남아야 한다.

## 위험·복원·승인할 범위

- 위험: 고치기가 「다른 물음」을 넓게 해석하면 정당한 정답 교체까지 멈출 수 있다. 셋을 명시해 줄였다. 첫 새 강의에서 본다.
- 복원: git revert 후 러너 재설치. 데이터 변경이 없다.
- 승인 범위: 위 파일의 로컬 구현·검사·Draft PR까지. master 병합(자동 배포)·러너 재설치·운영 재출제는 제외한다.
