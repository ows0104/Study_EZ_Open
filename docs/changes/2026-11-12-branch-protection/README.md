# master 서버측 브랜치 보호

## 의도

사용자 2026-11-12: 「지금 Github Test를 통과 못한 PR들이 Merge되어있는데 괜찮은거야?」
→ 조사 결과 설명 뒤 「Yes, set it up」(필수 검사 보호 적용), 「Yes, update the doc」(문서 반영).

조사(2026-11-12, 머지된 PR #122–#136과 master push 실행):
- 실제 테스트 실패로 병합된 것은 #124 하나. `tests/contracts/test_tier_from_importance.py`에서
  `KeyError: 'questions'`. master 실행도 `Tests and build`에서 실패해 배포는 건너뛰었고,
  #125가 7분 뒤 고쳐 배포했다.
- #119·#120·#130의 master 실행 실패는 `ci_deploy.py`가 「더 새 master 커밋이 있다」며 배포를
  일부러 거부한 것(테스트는 통과).
- #131·#135의 PR 쪽 「cancelled」, #134의 「skipped」(Draft·#135에 포함돼 병합 표시)는 master
  실행에서 테스트·배포가 성공했다.
- master에는 보호가 없었다. 저장소가 공개 상태여서 이전(2026-11-08)의 403 없이 설정할 수 있었다.

## 바꾼 것

1. **GitHub 설정(2026-11-12 적용, 저장소 파일 밖)**: `PUT repos/ows0104/Study_EZ_Open/branches/master/protection`
   - 필수 검사 `Tests and build`, `Windows runner checks`(GitHub Actions 앱), strict 끔
   - `enforce_admins` 켬, 강제 push·삭제 금지, 리뷰 필수 없음
   - 적용 직후 열린 PR: #138(`Tests and build` 실패)이 BLOCKED, #137(통과)은 CLEAN으로 확인.
2. **`docs/development/collaboration.md`**: 「master 보호 (로컬 훅)」 절을 서버측 보호 + 로컬 훅으로
   나누고, 「비공개·무료라 403」 설명과 작업 방법 끝 문단을 현재 상태로 고쳤다.
3. **`.githooks/pre-push`** 머리 주석: 서버측 보호가 생겼고 DASHBOARD.md 검사는 훅에만 있다고 적었다.
   동작은 그대로다(설치본을 다시 깔 필요 없음).

4. **Actions 분 설명**: 사용자 2026-11-12 「공개 전환은 의도한 거야, 분 설명도 고쳐줘」.
   공개 저장소는 GitHub 기본 실행기 분이 차감되지 않으므로 「비공개라 월 한도에서 빠진다」·
   「Windows 분 2배」를 과거 사정으로 돌렸다. `collaboration.md`(실행 범위·「PR 습관」 절, 제목과
   앵커 변경), `CLAUDE.md`·`AGENTS.md`(PR 습관 한 줄의 이유와 링크), `deploy.yml`·`scripts/ci_scope.py`
   주석. PR 습관 자체(Draft·묶어 push·문서 PR 묶기)는 바꾸지 않았다. 이유를 검사 대기 시간으로 바꿨을 뿐이며,
   습관을 완화할지는 사용자 결정으로 남긴다.
