# 사람 승인을 되돌릴 수 없는 작업으로 좁히기 — 설계

## 요구사항과 수용 기준
- CLAUDE.md 개발 루프 줄에서 「(사람 승인)」「(중요 승인)」을 빼고, 따로 묻는 것은 목록뿐이라고 쓴다.
- README의 Implementation Plan·Deploy 단계, 근거 기록 문단, 배포 절이 같은 뜻을 쓴다.
- collaboration.md·release-and-incidents.md·deployment.md는 같은 목록을 링크한다.

## 책임·입출력 계약·오류 상태
- `development.py approve --evidence`에는 사용자가 실제로 한 요청·승인 발언을 그대로 적는다. 발언을 지어내거나 제보·자동화·다른 세션의 말을 쓰지 않는 규칙은 유지한다.

## 호환성과 데이터 보존
- 도구·검사·state.json 형식은 바뀌지 않는다. 기존 작업의 승인 기록은 그대로 둔다.
