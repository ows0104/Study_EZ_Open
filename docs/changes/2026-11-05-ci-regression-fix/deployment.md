# 배포 및 사후 확인 완료

확인일: 2026-11-05 18:50 KST. 승인된 수정 및 배포 범위를 완료했다.

- 수정 PR: [#4](https://github.com/ows0104/Study_EZ_Open/pull/4), merge 완료.
- 수정 커밋: `0ebdd867a41201b05b8176da536a48cdf9a47d57`.
- 배포 master SHA: `d5e30590f138dddfe112f30176f7520a9d63ebdb`.
- [PR 검사](https://github.com/ows0104/Study_EZ_Open/actions/runs/42001992848): 성공.
- [master 검사 및 API 배포](https://github.com/ows0104/Study_EZ_Open/actions/runs/42003615259): 모두 성공.
- Python 회귀 검사: 1923 passed / 1 skipped. 계약: 125 passed. 서버: 107개 파일 통과. 연결·배포 보호: 95 passed. 웹 빌드 성공.

## API 배포 영수증

- revision: `studyez-api-release-420036152591`, 배포 상태 success.
- artifact SHA-256: `633d9b89681831caafc917efd0f6da63ef89af8cfeb35b39662cb60ef9a33ff5`.
- 이전 트래픽: `studyez-api-release-419867452801` 100%.
- 영수증: 위 Actions의 `deployment-d5e30590f138dddfe112f30176f7520a9d63ebdb-1` artifact.
- 독립 읽기 전용 확인: `/api/health`에서 status=ok, environment=production, revision이 위 master SHA와 일치했다. `/api/me`, `/api/timetable`, `/api/spotter/db`는 모두 무인증 401을 반환했다.

## 웹 배포

- Cloudflare Pages의 위 master SHA 체크: Deploy successful.
- 배포 ID: `0d52780a-db50-4fcf-99ed-b34bb009238c`.
- [배포 실행](https://dash.cloudflare.com/?to=/d0ec59549fea0c13f1b7fe9f724df93b/pages/view/study-ez-open/0d52780a-db50-4fcf-99ed-b34bb009238c).
- [운영 도메인](https://studyez.kr), [Pages 운영 주소](https://study-ez-open.pages.dev), [배포 고유 주소](https://0d52780a.study-ez-open.pages.dev)가 모두 HTTP 200을 반환했다.
- 세 주소의 JS/CSS 참조가 `/assets/index-BNidNBl1.js`, `/assets/index-Cs-eucWM.css`로 일치했다.

## 보존 및 한계

운영 데이터·문항·학습 기록·권한·비밀값을 변경하지 않았다. 로컬 러너 설치 및 재시작은 실행하지 않았다. 사후 확인은 공개 웹 응답, 배포 파일 참조, API 버전과 무인증 보호 경로에 한정하며 실제 사용자의 로그인·학습 기록 쓰기를 수행하지 않았다. 검증 원본 로그와 영수증은 로컬 `runs/_development/2026-11-05-ci-regression-fix/`에도 보존했다.

이 사후 기록은 이미 배포한 코드와 검사 근거를 변경하지 않는다. 추가 master 문서 merge로 중복 배포를 만들지 않도록 기존 수정 브랜치에 보존하고 dashboard 완료 행에서 연결한다.
