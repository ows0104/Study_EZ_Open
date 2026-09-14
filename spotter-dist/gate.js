/* 로그인 문. **Spotter의 다섯 과목이 이 파일 하나를 같이 쓴다.**
 *
 * 과목마다 화면이 다르게 생겼지만(기생충학은 사지선다, 해부학은 라벨링) 문은
 * 같아야 한다 — 한 번 로그인하면 다섯이 다 열리고, Study_EZ까지 열린다.
 * 그래서 로그인 화면·토큰 갱신·API 호출·사진 서명을 여기 모았다.
 *
 * 쓰는 쪽은 이것만 하면 된다:
 *
 *     GATE.start('exam1', async (db) => {  ...화면을 세운다...  });
 *
 * 콜백은 **로그인이 끝난 뒤에만** 불린다. 그 전에는 로그인 화면이 떠 있고
 * 문항 DB도 안 받아 온다 — 로그인 없이 자료가 나가는 우회로를 남기지 않는다.
 *
 * 사진은 `GATE.image(name)`으로 받는다. 서명 URL이라 미리 받아 두어야 하고,
 * 그 창을 미는 것도 여기서 한다.
 */
const GATE = (() => {
  const API = (CONFIG.apiBase || '').replace(/\/$/, '');
  const LOCAL_TEST = (CONFIG.localTestToken || '').trim();
  let subject = '';
  let signed = {};          // 파일명 → 서명 URL

  /* 화면 상태. **`return` 보다 위에 둔다** — 아래에 두면 IIFE가 거기서 끝나
     버려서 `let`이 초기화되지 않고, 첫 로그인에서 TDZ 오류가 난다. 함수
     선언은 끌어올려지므로 아래에 있어도 되지만 이 셋은 아니다. */
  const LABEL = { signin:'로그인', signup:'가입', reset:'비밀번호 재설정', recovery:'새 비밀번호 저장' };
  let mode = 'signin';
  let onReady = null;
  let started = false;   // `start()` 가 한 번이라도 불렸나

  /* ── 서버 ─────────────────────────────────────────────── */

  async function api(path, init = {}) {
    const token = LOCAL_TEST || (await AUTH.token());
    const r = await fetch(API + path, {
      ...init,
      headers: {
        ...(init.body ? { 'Content-Type': 'application/json' } : {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(init.headers || {}),
      },
    });
    if (r.status === 204) return null;
    const text = await r.text();
    const data = text ? JSON.parse(text) : null;
    if (!r.ok) {
      // 세션이 죽었으면 로그인 화면으로 돌린다. 여기서 안 잡으면 화면마다
      // "요청이 실패했습니다"만 뜨고 왜인지가 안 보인다.
      if (r.status === 401 && !LOCAL_TEST) { await AUTH.signOut(); location.reload(); }
      const detail = data && data.detail;
      throw new Error(typeof detail === 'string' ? detail : '요청이 실패했습니다.');
    }
    return data;
  }

  /* ── 사진 ─────────────────────────────────────────────── */

  /** 이 이름들의 서명 URL을 받아 둔다. 이미 받은 것은 건너뛴다. */
  async function sign(names) {
    const want = [...new Set(names)].filter(n => n && !signed[n]);
    for (let i = 0; i < want.length; i += 100) {
      const { urls } = await api(`/api/spotter/subjects/${subject}/images/sign`,
        { method: 'POST', body: JSON.stringify({ names: want.slice(i, i + 100) }) });
      Object.assign(signed, urls);
    }
  }

  /* 서명은 한 시간짜리라 한 판이 길어지면 만료된다. 화면이 사진을 못 그리면
     여기서 한 번 통째로 다시 받는다 — 만료를 시계로 재지 않는 이유는, 탭을
     재웠다 깨우면 시계가 못 믿을 것이 되기 때문이다. */
  function forget() { signed = {}; }

  return {
    /** 지금 화면이 쓸 사진 이름들을 미리 서명해 둔다. 창을 밀 때마다 부른다. */
    prefetch: names => sign(names),

    /** 서명된 주소. 아직 없으면 빈 문자열이니 `prefetch`를 먼저 부른다. */
    image: name => signed[name] || '',

    forget,
    api,
    get subject() { return subject; },

    /**
     * 문을 연다. 로그인이 끝나면 문항 DB를 받아 `ready(db)`를 부른다.
     *
     * `ready`가 불리기 전까지 화면 본문은 `hidden` 이다 — 각 과목의 HTML이
     * 자기 본문을 `<div id="app" hidden>` 으로 감싸고 있어야 한다.
     */
    async start(name, ready) {
      started = true;
      subject = name;
      /* **콜백을 여기서 붙잡아 둔다.** 아래 세 갈래(설정 없음·재설정·로그인
         화면)는 `enter`를 안 거치고 돌아가는데, `onReady`를 `enter` 안에서만
         세우면 그 세 갈래를 지난 뒤 폼에서 로그인했을 때 넘길 것이 남지
         않는다 — 문항 DB는 잘 받아 놓고 `onReady(db)`에서 터져서 화면이
         빈 채로 선다. 새로고침하면 세션이 있으니 곧장 `enter`로 가서
         멀쩡해지는, 첫 로그인에서만 나는 고장이었다. */
      onReady = ready || onReady;
      mountGate();

      if (!LOCAL_TEST) {
        if (!AUTH.ready) return fail(
          '로그인 설정이 없습니다. config.js의 supabaseUrl과 supabaseAnonKey를 채워 주세요.');
        if (AUTH.grabRecovery()) return setMode('recovery');
        if (!AUTH.session) return setMode('signin');
      }
      await enter(ready);
    },
  };

  /* ── 화면 ─────────────────────────────────────────────── */

  /* **문서가 서자마자 덮는다.** 과목 화면은 `window.onload`에서 문을 여는데,
     그 사이에 시작 화면이 한 번 그려졌다가 로그인 화면으로 바뀐다. 눈에 띄는
     깜빡임이고, 무엇보다 "로그인이 필요한 곳"처럼 안 보인다.

     덮개가 먼저 서면 순서가 뒤집힌다 — 로그인 화면이 먼저고, 통과한 뒤에
     과목 화면이 나온다. 이미 로그인한 사람에게는 「확인하는 중」이 잠깐
     스칠 뿐이다. */
  document.addEventListener('DOMContentLoaded', () => {
    // **이미 시작했으면 끼어들지 않는다.** 과목 화면은 `window.onload`에서
    // 문을 열지만(그때는 이 덮개가 먼저다), 문서 끝에서 바로 여는 화면도
    // 있다 — 그쪽은 이 시점에 이미 로그인 폼을 띄워 놓았고, 여기서 덮으면
    // 그 폼이 「확인하는 중」으로 가려진다.
    if (started) return;
    mountGate();
    show();
    $('gate-form').hidden = true;
    $('gate-note').textContent = '확인하는 중…';
  });

  function $(id) { return document.getElementById(id); }

  /* 글꼴도 Study_EZ가 받는 곳에서 같은 판을 받는다. 이름만 적어 두면 윈도우에서
     맑은 고딕으로 떨어지는데, 그러면 자간도 숫자 폭도 달라져서 같은 화면으로
     안 보인다. 못 받으면 아래 대체 글꼴로 떨어질 뿐 문이 막히지는 않는다. */
  function mountFont() {
    if (document.getElementById('gate-font')) return;
    const link = document.createElement('link');
    link.id = 'gate-font';
    link.rel = 'stylesheet';
    link.href = 'https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/'
      + 'dist/web/variable/pretendardvariable-dynamic-subset.min.css';
    document.head.append(link);
  }

  /** 로그인 화면을 문서에 심는다. 과목마다 HTML을 베끼지 않으려고 여기서 만든다. */
  function mountGate() {
    if ($('gate-root')) return;
    mountFont();
    const el = document.createElement('div');
    el.id = 'gate-root';
    el.hidden = true;
    el.innerHTML = `
<style>
  /* **Study_EZ의 로그인 화면과 같은 옷이다.** 한 계정으로 두 사이트가 열리는데
     문이 서로 다르게 생기면 같은 계정이라는 말이 안 믿긴다. 그래서 값을 눈대중
     맞춘 게 아니라 저쪽 web/src/styles/base.css의 토큰과 .gate 규칙을
     그대로 옮겨 왔다 — 고칠 일이 생기면 두 곳을 같이 고친다.

     여기서 달라진 것은 셋뿐이고, 다 옮기는 과정에서 어쩔 수 없었던 것이다:
     토큰을 :root 가 아니라 #gate-root 에 매단 것(이 덮개는 자기 스타일을
     가진 과목 화면 위에 얹히므로 밖으로 새면 안 된다), 초록 강조색을 버린 것,
     카드를 걷은 것. */
  #gate-root{
    --bg:#fbfbfc; --surface:#ffffff; --surface-2:#f6f7f9; --surface-3:#eceef1;
    --line:#e4e6ea; --line-strong:#d3d7dd;
    --ink:#16181d; --ink-2:#565b64; --ink-3:#878d97;
    --accent:#3e63dd; --accent-ink:#3a5bc7; --accent-line:#c1d0ff; --on-accent:#fff;
    --warn:#9a3412;
    --r-2:8px;
    --ring:0 0 0 2px var(--bg),0 0 0 4px var(--accent-line);
    position:fixed;inset:0;z-index:9999;overflow:auto;
    color-scheme:light;background:var(--bg);color:var(--ink);
    font-family:"Pretendard Variable",Pretendard,-apple-system,BlinkMacSystemFont,
      "Segoe UI","Apple SD Gothic Neo","Malgun Gothic",system-ui,sans-serif;
    font-size:15px;line-height:1.55;font-feature-settings:"cv05" 1;
    -webkit-font-smoothing:antialiased}
  /* 다크는 색을 뒤집는 게 아니라 같은 층 구조를 어두운 쪽에서 다시 세운 것이다. */
  @media (prefers-color-scheme:dark){#gate-root{
    --bg:#0d0e11; --surface:#15171b; --surface-2:#1a1d22; --surface-3:#23262c;
    --line:#272a31; --line-strong:#363a43;
    --ink:#eceef1; --ink-2:#a8aeb8; --ink-3:#757c88;
    --accent:#3e63dd; --accent-ink:#9eb1ff; --accent-line:#304384;
    --warn:#f0a06a;
    color-scheme:dark}}
  #gate-root .box{max-width:340px;margin:16vh auto 0;padding:0 20px;text-align:center}
  #gate-root h1{margin:0 0 4px;font-size:22px;font-weight:650;letter-spacing:-.021em}
  #gate-root .sub{margin:0 0 24px;color:var(--ink-3);font-size:12px}
  #gate-root form{display:grid;gap:8px;text-align:left}
  #gate-root label{display:block}
  /* [hidden] 은 브라우저 기본 규칙이라 바로 위의 #gate-root label 에 진다.
     재설정 갈래에서 비밀번호 칸을 숨겼는데도 그대로 서 있던 것이 이것이다 —
     required 만 꺼져서 폼은 넘어가고, 화면에는 안 쓰는 칸이 남았다. */
  #gate-root [hidden]{display:none}
  #gate-root label span{display:block;margin-bottom:4px;
    color:var(--ink-3);font-size:12px;font-weight:600}
  #gate-root input{width:100%;min-height:32px;padding:0 10px;box-sizing:border-box;
    border:1px solid var(--line);border-radius:var(--r-2);
    background:var(--surface);color:inherit;font:inherit;font-size:13px}
  #gate-root button{display:inline-flex;gap:6px;align-items:center;justify-content:center;
    width:100%;min-height:32px;padding:0 12px;
    border:1px solid var(--line);border-radius:var(--r-2);
    color:var(--ink-2);background:var(--surface);font:inherit;font-size:13px;font-weight:550;
    cursor:pointer;transition:background .12s ease,border-color .12s ease,color .12s ease}
  #gate-root button:hover:not(:disabled){
    border-color:var(--line-strong);color:var(--ink);background:var(--surface-2)}
  #gate-root button:disabled{opacity:.45;cursor:default}
  #gate-root button.primary{margin-top:4px;border-color:transparent;
    color:var(--on-accent);background:var(--accent)}
  #gate-root button.primary:hover:not(:disabled){border-color:transparent;
    color:var(--on-accent);background:var(--accent-ink)}
  #gate-root input:focus-visible,#gate-root button:focus-visible{outline:none;box-shadow:var(--ring)}
  #gate-root input:focus-visible{border-color:var(--accent)}
  /* 갈래를 바꾸는 단추는 밑줄이 아니라 조용한 단추다(저쪽 button.is-quiet). */
  #gate-root .switch{display:flex;gap:4px;margin-top:14px;justify-content:center;flex-wrap:wrap}
  #gate-root .switch button{width:auto;border-color:transparent;background:transparent;font-size:12px}
  #gate-root .switch button:hover:not(:disabled){border-color:transparent;background:var(--surface-3)}
  #gate-root .msg{margin:10px 0 0;color:var(--ink-2);font-size:13px;line-height:1.6}
  #gate-root .msg.bad{color:var(--warn);font-size:12px}
  /* 빈 줄이 자리를 차지하면 단추와 갈래 사이가 이유 없이 벌어진다. */
  #gate-root .msg:empty{display:none}
  #gate-root .foot{margin-top:32px;color:var(--ink-3);font-size:11px;line-height:1.6}
</style>
<div class="box">
  <h1>Spotter</h1>
  <p class="sub">같은 계정으로 Study_EZ에도 로그인합니다.</p>
  <form id="gate-form">
    <label id="gate-email-row"><span>이메일</span>
      <input type="email" id="gate-email" autocomplete="email" required></label>
    <label id="gate-pw-row"><span>비밀번호</span>
      <input type="password" id="gate-pw" minlength="8" autocomplete="current-password" required></label>
    <button type="submit" id="gate-submit" class="primary">로그인</button>
  </form>
  <p class="msg" id="gate-note"></p>
  <p class="msg bad" id="gate-error"></p>
  <div class="switch" id="gate-switch"></div>
  <p class="foot">가입하면 바로 쓸 수 있습니다. 승인은 따로 필요 없습니다.</p>
</div>`;
    /* **`body` 밑이 아니라 `html` 밑에 단다.** 화면이 자기 본문을 통째로
       숨기고 문을 여는 경우가 있는데(과목 고르는 허브가 그렇다), 덮개가
       본문 안에 있으면 같이 숨어서 로그인 화면이 안 보인다. */
    document.documentElement.append(el);
    $('gate-form').addEventListener('submit', submit);
  }


  function show() { $('gate-root').hidden = false; }

  function fail(message) {
    show();
    $('gate-form').hidden = true;
    $('gate-switch').innerHTML = '';
    $('gate-note').textContent = message;
  }

  function setMode(next) {
    mode = next;
    show();
    $('gate-form').hidden = false;
    $('gate-submit').textContent = LABEL[next];
    $('gate-submit').disabled = false;
    $('gate-note').textContent = next === 'recovery' ? '새 비밀번호를 정해 주세요.' : '';
    $('gate-error').textContent = '';
    // 숨긴 칸의 `required`는 같이 꺼야 한다. 안 그러면 브라우저가 폼을 막는데
    // 초점을 줄 수 없는 칸이라 경고도 안 뜬다 — 눌러도 아무 일이 안 일어난다.
    const needEmail = next !== 'recovery', needPw = next !== 'reset';
    $('gate-email-row').hidden = !needEmail;
    $('gate-pw-row').hidden = !needPw;
    $('gate-email').required = needEmail;
    $('gate-pw').required = needPw;
    $('gate-pw').autocomplete = next === 'signin' ? 'current-password' : 'new-password';
    $('gate-switch').innerHTML = next === 'recovery' ? '' :
      ['signin','signup','reset'].filter(m => m !== next)
        .map(m => `<button type="button" data-mode="${m}">${LABEL[m]}</button>`).join('');
    [...$('gate-switch').querySelectorAll('button')]
      .forEach(b => b.onclick = () => setMode(b.dataset.mode));
  }

  async function submit(event) {
    event.preventDefault();
    const email = $('gate-email').value.trim();
    const password = $('gate-pw').value;
    $('gate-submit').disabled = true;
    $('gate-error').textContent = '';
    $('gate-note').textContent = '';
    try {
      if (mode === 'reset') {
        await AUTH.reset(email);
        $('gate-note').textContent = '재설정 메일을 보냈습니다. 메일의 링크로 새 비밀번호를 정해 주세요.';
      } else if (mode === 'recovery') {
        await AUTH.setPassword(password);
        return enter(onReady);
      } else if (mode === 'signin') {
        await AUTH.signIn(email, password);
        return enter(onReady);
      } else {
        const session = await AUTH.signUp(email, password);
        if (session) return enter(onReady);
        // 확인 메일이 켜져 있으면 세션이 바로 안 나온다.
        $('gate-note').textContent = '가입 확인 메일을 보냈습니다. 링크를 누른 뒤 로그인해 주세요.';
      }
    } catch (e) {
      $('gate-error').textContent = e.message;
    }
    $('gate-submit').disabled = false;
  }

  /** 로그인이 끝났다. 문항 DB를 받아 화면에 넘긴다. */
  async function enter(ready) {
    onReady = ready || onReady;
    $('gate-note').textContent = subject ? '문항을 불러오는 중…' : '확인하는 중…';
    $('gate-form').hidden = true;
    $('gate-switch').innerHTML = '';
    show();
    try {
      /* 과목을 안 준 화면(과목 고르는 허브)은 **문항 DB를 안 받는다.**
         로그인만 확인하면 되는데 5.4MB를 받아 버리면 카드 다섯 장 보자고
         한 과목의 문항을 통째로 끌어오는 셈이고, 그 과목이 아직 안 올라온
         날에는 허브까지 같이 죽는다. `/api/me`가 그 확인의 최소 단위다. */
      const db = subject
        ? await api(`/api/spotter/subjects/${subject}/db`)
        : await api('/api/me');
      /* **화면을 다 세운 뒤에 덮개를 걷는다.** 먼저 걷으면 그 사이에 터진
         오류를 적을 자리가 이미 숨어 있어서, 남는 것은 빈 화면뿐이다. */
      await onReady(db);
      $('gate-root').hidden = true;
    } catch (e) {
      show();
      $('gate-form').hidden = true;
      $('gate-switch').innerHTML = '';
      $('gate-note').textContent = '';
      $('gate-error').textContent = e.message;
    }
  }
})();
