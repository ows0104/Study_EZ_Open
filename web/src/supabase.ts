import { createClient, type SupabaseClient } from "@supabase/supabase-js";

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
 */
export const supabase: SupabaseClient | null =
  url && anonKey ? createClient(url, anonKey, { auth: { persistSession: true, autoRefreshToken: true } }) : null;
