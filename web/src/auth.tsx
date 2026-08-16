import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import type { Session } from "@supabase/supabase-js";
import { LOCAL_TEST_TOKEN } from "./localTest";
import { supabase } from "./supabase";

type AuthState = {
  session: Session | null;
  loading: boolean;
  email: string;
  signOut: () => Promise<void>;
};

const AuthContext = createContext<AuthState>({
  session: null,
  loading: true,
  email: "",
  signOut: async () => {},
});

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (LOCAL_TEST_TOKEN) {
      // 서버가 local-test 모드일 때만 통하는 갈래다. 배포에서는 이 값이 없다.
      setSession({ user: { email: "local-test" } } as Session);
      setLoading(false);
      return;
    }
    if (!supabase) {
      setLoading(false);
      return;
    }
    supabase.auth.getSession().then(({ data }) => {
      setSession(data.session);
      setLoading(false);
    });
    const { data } = supabase.auth.onAuthStateChange((_event, next) => setSession(next));
    return () => data.subscription.unsubscribe();
  }, []);

  const value = useMemo<AuthState>(
    () => ({
      session,
      loading,
      email: session?.user.email ?? "",
      signOut: async () => {
        await supabase?.auth.signOut();
      },
    }),
    [session, loading],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  return useContext(AuthContext);
}

/**
 * 로그인 화면.
 *
 * 매직 링크 하나다. 비밀번호를 두면 해시·재설정·회전을 우리가 떠맡게 되고,
 * 그것이 인증을 자체 구현하지 않기로 한 이유를 그대로 되돌린다.
 */
export function LoginPage() {
  const [email, setEmail] = useState("");
  const [state, setState] = useState<"idle" | "sending" | "sent">("idle");
  const [error, setError] = useState("");

  if (!supabase) {
    return (
      <main className="gate">
        <h1>Study_EZ</h1>
        <p className="gate-note">
          로그인 설정이 없습니다. <code>VITE_SUPABASE_URL</code>과 <code>VITE_SUPABASE_ANON_KEY</code>를
          채워 주세요.
        </p>
      </main>
    );
  }

  async function send(event: React.FormEvent) {
    event.preventDefault();
    setError("");
    setState("sending");
    const { error: sendError } = await supabase!.auth.signInWithOtp({
      email,
      options: { emailRedirectTo: window.location.origin },
    });
    if (sendError) {
      setError(sendError.message);
      setState("idle");
      return;
    }
    setState("sent");
  }

  return (
    <main className="gate">
      <h1>Study_EZ</h1>
      {state === "sent" ? (
        <p className="gate-note">
          <strong>{email}</strong>으로 로그인 링크를 보냈습니다. 메일함을 확인해 주세요.
        </p>
      ) : (
        <form onSubmit={send}>
          <label htmlFor="email">학교 메일</label>
          <input
            id="email"
            type="email"
            value={email}
            required
            autoComplete="email"
            placeholder="name@snu.ac.kr"
            onChange={(event) => setEmail(event.target.value)}
          />
          <button type="submit" disabled={state === "sending"}>
            {state === "sending" ? "보내는 중…" : "로그인 링크 받기"}
          </button>
          {error ? <p className="gate-error">{error}</p> : null}
        </form>
      )}
      <p className="gate-fineprint">
        강의 자료는 제3자 저작물입니다. 로그인한 사람에게만, 짧은 수명의 링크로만 열립니다.
      </p>
    </main>
  );
}
