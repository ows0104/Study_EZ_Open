/**
 * Supabase 없이 화면을 굴려 보기 위한 갈래.
 *
 * 이 토큰은 서버가 `ENVIRONMENT=local-test`일 때만 통한다. 배포된 서버는
 * Supabase 서명을 검사하므로 여기에 무엇을 넣어도 401이다 — 로그인 필수라는
 * 규칙에 구멍을 내지 않는다는 뜻이다.
 *
 * 빌드 시점에 값이 없으면 코드째로 사라진다.
 */
export const LOCAL_TEST_TOKEN: string = import.meta.env.VITE_LOCAL_TEST_TOKEN ?? "";
