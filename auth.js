/* 로그인. Supabase(GoTrue)의 REST를 직접 두드린다.
 *
 * **라이브러리를 안 쓴다.** Study_EZ는 React라 `@supabase/auth-js`를 번들하지만
 * 여기는 빌드 도구가 없는 정적 파일 넷이고, 그 성질을 지키는 값이 크다 —
 * 문항을 고친 사람이 `npm`을 몰라도 화면을 고칠 수 있다. 우리가 쓰는 것은
 * 토큰 발급·갱신·비밀번호 재설정 넷뿐이라 아래 백 줄이면 된다.
 *
 * 비밀번호 해시도 재설정 메일도 우리가 만들지 않는다. 여기서 받는 것은 액세스
 * 토큰 하나이고, 서버는 그것을 검증만 한다. 그 원칙은 Study_EZ와 같다.
 *
 * **매직링크(OTP)를 안 쓰는 이유**도 같다 — 로그인할 때마다 메일이 한 통씩
 * 나가는데 Supabase 기본 발송은 시간당 몇 통이 한계라 한 학년이 쓰면 첫날에
 * 막힌다. 비밀번호 방식은 가입 확인과 재설정 때만 메일을 쓴다.
 */
const AUTH = (() => {
  const base = (CONFIG.supabaseUrl || '').trim().replace(/\/$/, '');
  const anon = (CONFIG.supabaseAnonKey || '').trim();
  const ready = !!(base && anon);

  /* 세션이 사는 자리. **Study_EZ와 같은 키, 같은 모양, 같은 쿠키다** —
     `session.js`가 그 규약이고 두 앱이 같은 파일을 쓴다. 서브도메인으로 갈려
     있어도 한 번 로그인하면 둘 다 열리는 것이 이 세 줄에서 나온다.

     모양은 auth-js가 저장하는 것을 따른다(GoTrue 토큰 응답 + `expires_at`).
     우리 형식을 쓰면 저쪽이 못 읽는다 — 라이브러리의 저장 형식을 우리가
     정할 수는 없으므로 맞추는 쪽이 우리다. */
  const store = ready
    ? SharedSession.cookieStorage({ domain: (CONFIG.sessionDomain || '').trim() })
    : null;
  const KEY = ready ? SharedSession.storageKey(base) : '';

  let session = null;
  try { session = JSON.parse((store && store.getItem(KEY)) || 'null'); } catch (e) {}

  const listeners = [];
  function set(next) {
    session = next;
    if (!store) { listeners.forEach(fn => fn(session)); return; }
    if (next) store.setItem(KEY, JSON.stringify(next));
    else store.removeItem(KEY);
    listeners.forEach(fn => fn(session));
  }

  /* 다른 앱이 갱신했을 수도 있다. 화면을 다시 그리기 전에 저장소를 한 번 본다 —
     탭을 오래 열어 둔 채 형제 앱에서 갱신이 일어나면 우리 손의 토큰이 이미
     지난 것일 수 있다. */
  function reload() {
    if (!store) return session;
    try { session = JSON.parse(store.getItem(KEY) || 'null'); } catch (e) {}
    return session;
  }

  async function call(path, body, token) {
    const r = await fetch(`${base}/auth/v1/${path}`, {
      method: 'POST',
      headers: {
        apikey: anon,
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token || anon}`,
      },
      body: JSON.stringify(body),
    });
    const text = await r.text();
    const data = text ? JSON.parse(text) : {};
    if (!r.ok) {
      // GoTrue는 자리에 따라 다른 칸에 이유를 적는다.
      throw new Error(data.error_description || data.msg || data.message || '요청이 실패했습니다.');
    }
    return data;
  }

  /** 토큰 응답 하나를 세션으로.
   *
   *  **응답을 통째로 들고 `expires_at`만 더한다.** auth-js가 저장하는 모양이
   *  그것이라서다 — 우리가 쓰는 칸만 골라 담으면 형제 앱이 그 세션을 집었을 때
   *  `user`가 없어서 화면이 빈다.
   */
  function adopt(data) {
    if (!data.access_token) return null;
    set({
      ...data,
      expires_at: Math.floor(Date.now() / 1000) + (data.expires_in || 3600),
      // 갱신 응답에는 user가 없을 수 있다. 들고 있던 것을 잃지 않는다.
      user: data.user || (session && session.user) || null,
    });
    return session;
  }

  /* 갱신은 한 번에 하나만 돈다. 화면이 뜨는 순간 여러 요청이 동시에 나가는데
     (문항 DB·내 상태·신고 목록) 각자 갱신을 부르면 리프레시 토큰이 회전하면서
     나중 것이 이미 쓰인 토큰을 들고 실패한다. */
  let refreshing = null;
  async function refresh() {
    if (!session || !session.refresh_token) { set(null); return null; }
    if (!refreshing) {
      refreshing = call('token?grant_type=refresh_token', { refresh_token: session.refresh_token })
        .then(adopt)
        .catch(() => { set(null); return null; })
        .finally(() => { refreshing = null; });
    }
    return refreshing;
  }

  /** API를 부르기 직전에 쓸 토큰. 만료가 가까우면 먼저 갱신한다.
   *
   *  **저장소를 먼저 다시 읽는다.** 형제 앱이 방금 갱신했으면 쿠키에 새 토큰이
   *  들어 있고, 우리가 들고 있던 것으로 갱신을 시도하면 회전된 리프레시 토큰을
   *  두 번 쓰는 셈이 된다.
   */
  async function token() {
    if (!reload()) return '';
    if (session.expires_at - Math.floor(Date.now() / 1000) < 90) {
      const next = await refresh();
      return next ? next.access_token : '';
    }
    return session.access_token;
  }

  return {
    ready,
    get session() { return session; },
    get email() { return (session && session.user && session.user.email) || ''; },
    token,
    onChange: fn => listeners.push(fn),

    signIn: (email, password) =>
      call('token?grant_type=password', { email, password }).then(adopt),

    /** 확인 메일이 켜져 있으면 세션이 바로 안 나온다. 그때는 null이 돌아온다. */
    signUp: (email, password) =>
      call('signup', { email, password }).then(d => (d.access_token ? adopt(d) : null)),

    /* 돌아올 주소를 같이 준다. Supabase의 **URL Configuration → Redirect URLs**에
       이 주소가 등록돼 있어야 링크가 살아 있다. 등록 안 하면 메일은 오는데
       링크가 죽는다. */
    reset: email =>
      call(`recover?redirect_to=${encodeURIComponent(location.origin + location.pathname)}`,
           { email }).then(() => true),

    signOut: async () => {
      const t = session && session.access_token;
      set(null);
      if (t) { try { await call('logout', {}, t); } catch (e) {} }
    },

    /** 재설정 메일의 링크로 돌아왔을 때. 주소창의 조각에 토큰이 실려 온다. */
    grabRecovery() {
      if (!location.hash.includes('access_token')) return false;
      const p = new URLSearchParams(location.hash.slice(1));
      const type = p.get('type');
      if (p.get('access_token')) {
        adopt({
          access_token: p.get('access_token'),
          refresh_token: p.get('refresh_token'),
          expires_in: +(p.get('expires_in') || 3600),
        });
      }
      // 토큰이 주소창에 남지 않게 지운다. 뒤로 가기에도 안 남는다.
      history.replaceState(null, '', location.pathname + location.search);
      return type === 'recovery';
    },

    /** 새 비밀번호를 정한다. 재설정 링크로 들어온 직후에만 부른다. */
    async setPassword(password) {
      const t = await token();
      if (!t) throw new Error('링크가 만료되었습니다. 재설정을 다시 요청해 주세요.');
      const r = await fetch(`${base}/auth/v1/user`, {
        method: 'PUT',
        headers: { apikey: anon, 'Content-Type': 'application/json', Authorization: `Bearer ${t}` },
        body: JSON.stringify({ password }),
      });
      const data = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(data.msg || data.message || '비밀번호를 바꾸지 못했습니다.');
      return true;
    },
  };
})();
