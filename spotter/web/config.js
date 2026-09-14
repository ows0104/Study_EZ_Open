/* 배포마다 다른 값 셋. 여기 있는 것이 곧 사실이다 —
   `scripts/upload_web.py`도 이 파일을 읽어서 어느 서버에 올릴지 정한다.

   **anon 키는 공개되어도 되는 값이다.** Supabase가 그렇게 설계돼 있고
   (Study_EZ의 `web/.env.example`도 같은 말을 한다), 실제 권한은 서버가 토큰을
   검증해서 정한다. 저장소에 그대로 두어도 된다.

   비워 두면 로그인 없이 `../build/`의 `quiz_db.json`과 `images/`를 바로 읽는
   갈래로 떨어진다. **localhost에서만 그렇다** — 배포된 주소에서 값이 비어 있으면
   화면이 "설정이 없습니다"를 띄우고 멈춘다. 자료가 로그인 없이 열리는
   우회로를 남기지 않기 위해서다. */
const CONFIG = {
  apiBase: 'https://studyez-api-97999573571.asia-northeast3.run.app',
  supabaseUrl: 'https://dlvruugdigpbtgiwpdgs.supabase.co',
  supabaseAnonKey: 'sb_publishable_cOcv3JFn7wtgjpSFjV89jA_OhhtTfJk',

  /* 세션 쿠키를 걸 등록 도메인. **Study_EZ의 `VITE_SESSION_DOMAIN`과 같아야
     한다** — 두 값이 어긋나면 로그인이 안 나눠진다. 이 호스트가 그 도메인
     아래가 아니면(로컬 개발, github.io) 자동으로 호스트 전용이 되고 공유만
     안 될 뿐 로그인은 그대로 된다. */
  sessionDomain: 'studyez.kr',

  /* 서버가 `ENVIRONMENT=local-test`로 떠 있을 때만 통하는 토큰. Study_EZ의
     `web/src/localTest.ts`와 같은 자리다 — Supabase 없이 서버까지 붙여서
     기록·제보까지 돌려 보려고 있다. **배포에서는 반드시 비운다.** */
  localTestToken: '',
};
