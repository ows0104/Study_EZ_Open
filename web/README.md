# Study_EZ 웹

화면 셋. Vite + React, Next.js RSC까지 갈 이유가 없다.

```
src/
  auth.tsx              Supabase 매직 링크. 로그인 없이 열리는 화면은 없다
  api.ts                토큰을 붙이는 fetch + 서명 URL 열기
  calendar/             / — 캘린더가 홈
  lecture/              /lectures/{과목}/{run_id} — 새 창
  admin/                /admin — 매칭 확인 · 업로드 현황 · 예습 링크
  styles/               흰 배경, 무채색, 강조색 하나
```

## 띄우기

```bash
npm install
cp .env.example .env.local    # 값을 채운다
npm run dev
```

`/api`는 개발 중 `localhost:8000`으로 프록시된다.

Supabase 없이 화면만 보려면 `.env.local`에 `VITE_LOCAL_TEST_TOKEN=local-test-token`을
두고 서버를 `ENVIRONMENT=local-test`로 띄운다. 이 토큰은 배포된 서버에서는
통하지 않는다.

## 강조색이 하나인 이유

색은 **"네가 열어 볼 것이 있다"** 하나만 뜻한다. 자료가 붙은 강의 칸에만
강조색이 들어가고 나머지는 전부 회색조다.

필기의 색을 읽지 않기로 한 것과 같은 판단이다 — 색이 여럿을 뜻하기 시작하면
아무것도 뜻하지 않게 되고, 그러면 근거로 못 쓴다. 칩의 점 세 개도 색이 아니라
채움(꽉 참 / 테두리만 / 네모)으로 가른다.

## 주소가 두 마디인 이유

```
/lectures/{과목}/{run_id}
```

설계 문서는 `/lectures/{run_id}`라 적었지만 `run_id`는 `260813_03` 같은
날짜_교시라서 **과목을 포함하지 않는다.** 한 교시에 여러 과목이 열리므로
`run_id` 단독으로는 강의를 특정할 수 없다. 서버 키가 `(subject, run_id)`
복합인 것과 같은 이유다.
