# Study_EZ 웹

Vite·React·TypeScript 프론트다. 캘린더, 강의 자료, 예습·복습 풀이,
Quiz Bank, 관리 화면, 공지와 이용방법을 제공한다.

## 실행

`web/` 폴더에서 실행한다.

```powershell
npm install
Copy-Item .env.example .env.local
npm run dev
```

[.env.example](.env.example)의 값을 `.env.local`에 채운다.
개발 중 `/api`는 `localhost:8000`으로 프록시된다.

Supabase 없이 로컬 화면을 확인하려면 `.env.local`에
`VITE_LOCAL_TEST_TOKEN=local-test-token`을 넣고,
[서버](../server/README.md)를 `ENVIRONMENT=local-test`로 실행한다.

## 수정·검사

파일 지도와 유지할 계약은 [CLAUDE.md](CLAUDE.md)에 있다.

```powershell
npm run typecheck
npm run build
```

개발·빌드 시작 시 `../bridge/`가 다운로드용 ZIP으로 묶인다.
`src/types/`는 API의 기능별 데이터 타입을 담는다.

## 라우트

| 주소 | 화면 |
|---|---|
| `/` | 캘린더 |
| `/study` | 강의 선택·연속 학습·관리자 원본 대조 요청 |
| `/lectures/:subject/:runId` | 강의 자료 |
| `/prequiz/:subject/:runId`, `/mainquiz/:subject/:runId` | 자기채점 퀴즈 |
| `/bank/:subject/:runId` | Quiz Bank |
| `/bank/:subject/:runId/all` | 전체 문제 · 슬라이드 순서 열람 |
| `/admin/*` | 관리자 |
| `/notices`, `/guide` | 공지·이용방법 |
| `/privacy` | 공개 개인정보처리방침 |

강의 식별에는 과목과 run ID가 함께 필요하다.
`public/_redirects`는 직접 열린 하위 경로를 `index.html`로 연결한다.

Cloudflare Pages 빌드는 `npm run build`, 출력은 `dist`다.
현재 배포 설정·검증 절차는 [Pages 실행서](../docs/cloudflare-pages-runbook.md)를 참고한다.
