# 배포 기록

- 2026-11-24 10:00Z PR #251 병합(6b1f5930). PR 뒤 master가 전진해(ed17efa2) master에서 전체 검사가 다시 돌았다.
- `tests/quizbank/test_connection_presuppose.py::test_nothing_presupposed_adds_nothing_and_keeps_the_medical_review`가
  모델 호출 순서(`v4-presuppose-0`·`v4-discriminate-0`)가 뒤바뀌어 실패했다. 이 PR은 웹만 바꿨고, 같은 검사가 PR·앞 병합에서 통과했다.
  코드 변경 없이 `gh run rerun --failed`로 통과 → API 배포 성공(health 6b1f5930).
- Cloudflare Pages는 API health를 15분 기다리다 10:16Z에 실패로 끝났고, GitHub 재실행으로는 다시 빌드되지 않는다
  (check-run rerequest는 404). 이 기록만 담은 문서 PR을 병합해 Pages가 새 master 커밋으로 다시 빌드하게 했다.
- 남은 일: 위 검사의 순서 의존(불안정) 고치기 — 출제 쪽 별도 작업.
