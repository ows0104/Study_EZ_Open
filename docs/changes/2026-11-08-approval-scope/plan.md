# 사람 승인을 되돌릴 수 없는 작업으로 좁히기 — 구현 계획

## 변경 범위·대상 파일·순서
CLAUDE.md, docs/development/README.md, docs/development/collaboration.md,
docs/development/release-and-incidents.md, docs/deployment.md의 승인 문구만 고친다.

## 검사 명령과 성공 조건
`python -m pytest tests/development -q` 통과. 바뀐 문서의 링크 앵커가 README 제목과 맞는지 확인.

## 위험·복원·승인할 범위
문서만이라 git revert로 되돌린다. 사람에게 묻는 목록에 닿는 일은 없다.
