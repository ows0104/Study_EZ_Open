# 복습 개인링크 문구 변경 — 배포 확인

- 사용자 승인: 2026-11-07 현재 채팅의 기본 프롬프트 교체 및 교수 안내 한 줄 축약 요청.
- 구현 revision: `6f7e020181713a6662b3eb2af1aa12cdf0c1acc7`.
- 병합 revision: `2d85e7936651ff6c3b7c83c2dda7c13ed9143215`, [PR #15](https://github.com/ows0104/Study_EZ_Open/pull/15).
- 로컬 검사: 복습 관련 Node 검사 5/5, 웹 typecheck/build, development.py release gate 통과.
- 전체 PR 검사: [42360035615](https://github.com/ows0104/Study_EZ_Open/actions/runs/42360035615) 성공.
- 병합 후 전체 검사·운영 API 배포: [42360807410](https://github.com/ows0104/Study_EZ_Open/actions/runs/42360807410) 모두 성공.
- [Cloudflare Pages 배포](https://dash.cloudflare.com/?to=/d0ec59549fea0c13f1b7fe9f724df93b/pages/view/study-ez-open/069cb4f7-8426-4fe7-9db3-09bf35755dbe) 성공. GitHub의 같은 SHA check-run으로 확인했다.
- 게시 전 공개 API revision `2489e52e6ff517d661e56d25c0f0ff6058384e8d`, 웹 HTTP 200.

## 확인할 최종 문구

```text
[261104_01] 포도알균(김범준)_박정수 v1.pdf
오늘 들은 강의를 복습하고 싶어. 첨부한 올해 필기와 족보를 바탕으로 큰 흐름을 설명해줘.

올해 담당 교수: 김범준
```

실제 첨부 파일명과 교수는 강의마다 치환한다. 기존에 저장한 개인 문구는 보존하고 기본값으로 되돌릴 때 새 기본 문구를 사용한다. 기존 개인 대화/첨부/은행/학습 기록 변경은 없다.

## Maintain / 실제 게시 후 확인

2026-11-07 18:52:57 KST(09:52:57 UTC) 공개 응답을 읽기 전용으로 확인했다.

- API health: `status=ok`, `environment=production`, revision `2d85e7936651ff6c3b7c83c2dda7c13ed9143215`.
- 공개 웹 HTTP 200, 실제 entry `/assets/index-CZYrF3bP.js` → `assets/ReviewAction-B_AZ-gLS.js`를 따라가 확인했다.
- 새 기본 문장과 `올해 담당 교수: `가 실제 배포 자산에 포함되었다. `복습 담당 교수 확인:`, 시간표 대조 설명, 실제 필기 교수로 재판단하라는 긴 문구는 없다.
- 무인증 `/api/me`는 401을 유지한다. 사용자 대화 생성·학습 사건·자료 쓰기는 실행하지 않았다.
- 변경 완료. 후속 이상은 별도 변경 기록으로 처리하고, 복원 필요 시 이 코드 변경의 revert PR을 사용한다.
