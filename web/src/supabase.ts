import { AuthClient, type GoTrueClient } from "@supabase/auth-js";
// 부작용으로 `globalThis.SharedSession`을 세운다. 빌드 도구가 없는 형제 앱
// (기생충학 땡시)이 같은 파일을 `<script src>`로 읽어야 해서 클래식 스크립트다.
import "../../platform/session/session.js";

const url = import.meta.env.VITE_SUPABASE_URL ?? "";
const anonKey = import.meta.env.VITE_SUPABASE_ANON_KEY ?? "";
// 세션 쿠키를 어느 도메인에 걸 것인가. 비우면 이 호스트 전용이 되고 형제 앱과
// 공유되지 않는다 — 로컬 개발과 `pages.dev` 비상 경로가 그 경우다.
const sessionDomain = import.meta.env.VITE_SESSION_DOMAIN ?? "";

type SharedSessionApi = {
  cookieStorage: (options: { domain: string }) => {
    getItem: (key: string) => string | null;
    setItem: (key: string, value: string) => void;
    removeItem: (key: string) => void;
  };
  storageKey: (supabaseUrl: string) => string;
};

const shared = (globalThis as unknown as { SharedSession: SharedSessionApi }).SharedSession;

/**
 * Supabase가 로그인을 맡는다.
 *
 * 비밀번호 해시도 재설정 메일도 우리가 만들지 않는다. 여기서 받는 것은
 * 액세스 토큰 하나이고, 서버는 그것을 검증만 한다.
 *
 * 설정이 없으면 null이다 — 화면이 "로그인 설정이 없습니다"를 띄우고 멈춘다.
 * 로그인 없이 자료를 보여 주는 우회로는 없다.
 *
 * **`createClient` 대신 `AuthClient`를 직접 세운다.** 이 앱이 Supabase에서 쓰는
 * 것은 auth 하나인데 `@supabase/supabase-js`의 `createClient`는 realtime·
 * phoenix·storage·postgrest·functions·iceberg를 통째로 끌고 온다 — 번들
 * 496KB 중 **약 100KB가 한 줄도 실행되지 않는 코드였다**(소스맵으로 셈).
 * DB도 스토리지도 우리 서버가 대신 두드리므로 앞으로도 쓸 일이 없다.
 *
 * 아래 세 값은 `createClient`가 `AuthClient`에 넘기던 것을 그대로 옮긴 것이다.
 * 나머지 기본값(autoRefreshToken·persistSession·detectSessionInUrl·flowType)은
 * auth-js 쪽 기본값이 supabase-js가 넘기던 값과 같아서 적지 않는다.
 *
 *   url        `new URL('auth/v1', 베이스)`
 *   headers    anon 키를 Authorization과 apikey 양쪽에
 *   storageKey `sb-<프로젝트 ref>-auth-token`
 *
 * **`storageKey`가 어긋나면 이미 로그인해 둔 사람이 전부 튕긴다.** 세션이 저 키로
 * localStorage에 들어 있다. 그래서 이름을 손으로 적지 않고 supabase-js와 같은
 * 방식으로 호스트에서 뽑는다.
 */
function client(): GoTrueClient | null {
  if (!url || !anonKey) return null;
  const base = new URL(url.trim().endsWith("/") ? url.trim() : `${url.trim()}/`);
  return new AuthClient({
    url: new URL("auth/v1", base).href,
    headers: { Authorization: `Bearer ${anonKey}`, apikey: anonKey },
    storageKey: shared.storageKey(base.href),
    /**
     * **세션을 localStorage가 아니라 쿠키에 둔다.**
     *
     * localStorage는 오리진마다 따로라, 형제 앱이 서브도메인으로 갈리면 같은
     * 계정인데도 로그인을 두 번 해야 한다. `Domain=.studyez.kr` 쿠키는 형제가
     * 같이 읽는다.
     *
     * 이미 로그인해 둔 사람은 안 튕긴다 — 어댑터가 처음 읽을 때 localStorage에
     * 남은 세션을 쿠키로 옮긴다.
     *
     * 대가가 하나 있다. **두 앱을 동시에 열어 두면 토큰 갱신이 겹칠 수 있다.**
     * Supabase는 리프레시 토큰을 회전시키므로 한쪽이 갱신한 직후 다른 쪽이 옛
     * 토큰으로 갱신하려 들 수 있고, 그때는 재사용 유예 창(기본 10초) 안이면
     * 통과하고 아니면 한쪽이 다시 로그인한다. 창을 늘리려면 Supabase의
     * Refresh Token Reuse Interval을 키운다.
     */
    storage: shared.cookieStorage({ domain: sessionDomain }),
  });
}

export const auth: GoTrueClient | null = client();
