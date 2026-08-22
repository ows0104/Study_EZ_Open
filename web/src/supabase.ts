import { AuthClient, type GoTrueClient } from "@supabase/auth-js";

const url = import.meta.env.VITE_SUPABASE_URL ?? "";
const anonKey = import.meta.env.VITE_SUPABASE_ANON_KEY ?? "";

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
    storageKey: `sb-${base.hostname.split(".")[0]}-auth-token`,
  });
}

export const auth: GoTrueClient | null = client();
