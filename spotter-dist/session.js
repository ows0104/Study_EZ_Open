/* 형제 앱이 로그인을 나눠 갖는 자리.
 *
 * Study_EZ와 땡시가 **같은 등록 도메인 아래 있을 때** 한 번 로그인하면 둘 다
 * 열린다. localStorage는 오리진마다 따로라 그걸로는 안 되고, `Domain=.studyez.kr`
 * 쿠키는 형제 서브도메인이 같이 읽는다. 그 차이가 이 파일의 전부다.
 *
 * **두 앱이 같은 키에 같은 모양으로 써야 한다.** 모양은 Supabase auth-js가
 * 저장하는 것을 따른다(`{access_token, refresh_token, expires_at, user, …}`의
 * JSON). 땡시는 auth-js를 안 쓰지만 그쪽에 맞춘다 — 이미 그 모양으로 저장하는
 * 쪽이 있고, 라이브러리의 저장 형식을 우리가 정할 수는 없기 때문이다.
 *
 * 쓰는 법:
 *
 *     const storage = SharedSession.cookieStorage({ domain: 'studyez.kr' });
 *     storage.getItem(SharedSession.storageKey(supabaseUrl));
 *
 * auth-js에는 `storage`로 그대로 넘기면 되고, 손으로 쓰는 쪽은
 * `getItem`/`setItem`/`removeItem`을 부르면 된다.
 *
 * 클래식 스크립트다(모듈 아님). 땡시가 `<script src>`로 읽고, Vite 쪽은
 * import해서 부작용으로 전역을 세운다 — 빌드 도구가 없는 앱과 있는 앱이
 * 같은 파일을 쓰려면 이 형태가 제일 덜 아프다.
 */
(function (root) {
  'use strict';

  /* 쿠키 하나의 상한은 브라우저마다 4KB 안팎이고, 한 세션 JSON은 보통
     2~3KB지만 user 객체가 커지면 넘는다. 넘을 때를 위해 나눠 담는다 —
     `@supabase/ssr`이 같은 이유로 같은 일을 한다. */
  const CHUNK = 3200;
  // 브라우저가 받아 주는 상한이 400일이다. 리프레시 토큰이 그보다 오래 산다.
  const MAX_AGE = 400 * 24 * 60 * 60;

  /** `sb-<프로젝트 ref>-auth-token`. auth-js가 쓰는 이름과 같아야 한다. */
  function storageKey(supabaseUrl) {
    const host = new URL(String(supabaseUrl)).hostname;
    return 'sb-' + host.split('.')[0] + '-auth-token';
  }

  function readAll() {
    const out = {};
    for (const part of (document.cookie || '').split('; ')) {
      const at = part.indexOf('=');
      if (at > 0) out[part.slice(0, at)] = part.slice(at + 1);
    }
    return out;
  }

  /* 도메인을 붙일 수 있는가.
   *
   * 붙일 수 있는 조건이 셋이다 — 값이 있고, 지금 호스트가 그 아래이고,
   * **점이 든 진짜 도메인**이어야 한다. 마지막 것이 실제로 물렸다:
   * `Domain=.localhost`를 주면 브라우저가 쿠키를 저장하지 않는다(IP 주소도
   * 같다). 붙일 수 없으면 호스트 전용 쿠키가 되고, 공유만 안 될 뿐 로그인은
   * 그대로 된다. */
  function scope(domain) {
    if (!domain || !domain.includes('.')) return '';
    if (/^[\d.]+$/.test(domain)) return '';
    const host = location.hostname;
    if (host === domain || host.endsWith('.' + domain)) return '; Domain=.' + domain;
    return '';
  }

  function cookieStorage(options) {
    const opts = options || {};
    const suffix =
      scope(opts.domain) +
      '; Path=/; SameSite=Lax' +
      // 로컬 http에서는 Secure를 붙이면 쿠키가 저장되지 않는다.
      (location.protocol === 'https:' ? '; Secure' : '');

    function write(name, value) {
      document.cookie = name + '=' + value + suffix + '; Max-Age=' + MAX_AGE;
    }
    function drop(name) {
      document.cookie = name + '=' + suffix + '; Max-Age=0';
    }

    /* 쿠키를 못 쓰는 자리로 밝혀졌는가. **써 보고 되읽어서 정한다.**
     *
     * 미리 알 방법이 없다 — 브라우저는 거부한 쿠키를 조용히 버리고 예외도
     * 안 던진다. 실제로 `Domain=.localhost`가 그렇게 통째로 사라졌고, 그때
     * 증상은 "로그인이 안 된다"가 아니라 "로그인이 안 남는다"였다. 한 번
     * 확인해서 아니면 localStorage로 떨어진다 — 공유는 잃지만 그 앱은 돈다. */
    let fallback = false;

    function stored(key) {
      const jar = readAll();
      if (jar[key + '.0'] !== undefined) {
        // 나눠 담긴 것. 빈 자리가 나올 때까지 이어 붙인다.
        const parts = [];
        for (let i = 0; jar[key + '.' + i] !== undefined; i++) parts.push(jar[key + '.' + i]);
        return parts.join('');
      }
      return jar[key];
    }

    const api = {
      getItem(key) {
        if (!fallback) {
          try {
            const raw = stored(key);
            if (raw !== undefined) return decodeURIComponent(raw);
          } catch (e) {
            /* 아래에서 localStorage를 본다. */
          }
        }

        /* 쿠키에 없다. localStorage를 보는 이유가 둘이다 — 쿠키를 못 쓰는
           자리로 떨어졌거나, **세션을 localStorage에 두던 때에 로그인해 둔
           사람**이거나. 뒤엣것을 안 보면 이 변경으로 전원이 한 번 튕긴다. */
        let local = null;
        try {
          local = localStorage.getItem(key);
        } catch (e) {
          return null;
        }
        if (local === null || fallback) return local;

        // 쿠키로 옮긴다. **옮기는 데 성공했을 때만** 원본을 지운다 —
        // 옮기다 떨어지면 방금 쓴 것을 지우는 셈이 된다.
        api.setItem(key, local);
        if (!fallback) {
          try {
            localStorage.removeItem(key);
          } catch (e) {
            /* 못 지워도 그만이다. 다음부터는 쿠키가 먼저 잡힌다. */
          }
        }
        return local;
      },

      setItem(key, value) {
        const text = String(value);
        if (!fallback) {
          const encoded = encodeURIComponent(text);
          try {
            const jar = readAll();
            // 지난번에 나눠 담았던 자리를 먼저 비운다. 안 그러면 짧아졌을 때
            // 남은 조각이 뒤에 붙어 JSON이 깨진다.
            for (let i = 0; jar[key + '.' + i] !== undefined; i++) drop(key + '.' + i);
            if (encoded.length <= CHUNK) {
              drop(key + '.0');
              write(key, encoded);
            } else {
              drop(key);
              for (let i = 0, at = 0; at < encoded.length; i++, at += CHUNK) {
                write(key + '.' + i, encoded.slice(at, at + CHUNK));
              }
            }
            if (stored(key) === encoded) return;   // 들어갔다. 끝.
          } catch (e) {
            /* 아래에서 localStorage로 떨어진다. */
          }
          fallback = true;
        }
        try {
          localStorage.setItem(key, text);
        } catch (e) {
          /* 여기까지 막혔으면 이 브라우저에는 남길 자리가 없다. 이번 탭에서만
             로그인이 유지되고, 새로 열면 다시 로그인한다. */
        }
      },

      removeItem(key) {
        try {
          const jar = readAll();
          for (let i = 0; jar[key + '.' + i] !== undefined; i++) drop(key + '.' + i);
        } catch (e) {
          /* 위와 같다. */
        }
        drop(key);
        try {
          localStorage.removeItem(key);
        } catch (e) {
          /* 위와 같다. */
        }
      },
    };
    return api;
  }

  root.SharedSession = { cookieStorage, storageKey };
})(typeof globalThis !== 'undefined' ? globalThis : self);
