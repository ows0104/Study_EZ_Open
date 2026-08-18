import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import type { Session } from "@supabase/supabase-js";
import { LOCAL_TEST_TOKEN } from "./localTest";
import { supabase } from "./supabase";
import { Link } from "react-router-dom";

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

type Mode = "signin" | "signup" | "reset";

const LABELS: Record<Mode, string> = {
  signin: "로그인",
  signup: "가입",
  reset: "비밀번호 재설정",
};

/**
 * 로그인 화면.
 *
 * 이메일과 비밀번호다. 매직링크가 화면은 더 단순하지만 **로그인할 때마다 메일이
 * 한 통씩 나간다.** Supabase 기본 발송은 시간당 몇 통이 한계라 한 학년이 쓰는
 * 사이트에서는 첫날에 막힌다. 비밀번호 방식은 가입과 재설정 때만 메일을 쓴다.
 *
 * 비번 해시도 재설정 흐름도 Supabase가 한다 — 인증을 자체 구현하지 않는다는
 * 원칙은 그대로다.
 */
export function LoginPage() {
  const [mode, setMode] = useState<Mode>("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
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

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setMessage("");
    try {
      if (mode === "reset") {
        const { error: failed } = await supabase!.auth.resetPasswordForEmail(email, {
          redirectTo: `${window.location.origin}/`,
        });
        if (failed) throw failed;
        setMessage("재설정 메일을 보냈습니다. 메일의 링크로 새 비밀번호를 정해 주세요.");
      } else if (mode === "signin") {
        const { error: failed } = await supabase!.auth.signInWithPassword({ email, password });
        if (failed) throw failed;
      } else {
        const { data, error: failed } = await supabase!.auth.signUp({ email, password });
        if (failed) throw failed;
        // 확인 메일이 켜져 있으면 세션이 바로 나오지 않는다.
        setMessage(
          data.session
            ? "가입했습니다. 관리자 승인을 기다려 주세요."
            : "가입 확인 메일을 보냈습니다. 링크를 누른 뒤 로그인해 주세요.",
        );
      }
    } catch (cause) {
      setError((cause as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="gate">
      <h1>Study_EZ</h1>
      <form onSubmit={submit}>
        <label htmlFor="email">이메일</label>
        <input
          id="email"
          type="email"
          value={email}
          required
          autoComplete="email"
          onChange={(event) => setEmail(event.target.value)}
        />

        {mode === "reset" ? null : (
          <>
            <label htmlFor="password">비밀번호</label>
            <input
              id="password"
              type="password"
              value={password}
              required
              minLength={8}
              autoComplete={mode === "signup" ? "new-password" : "current-password"}
              onChange={(event) => setPassword(event.target.value)}
            />
          </>
        )}

        <button type="submit" disabled={busy}>
          {busy ? "잠시만요…" : LABELS[mode]}
        </button>

        {error ? <p className="gate-error">{error}</p> : null}
        {message ? <p className="gate-note">{message}</p> : null}
      </form>

      <div className="gate-switch">
        {(["signin", "signup", "reset"] as Mode[])
          .filter((next) => next !== mode)
          .map((next) => (
            <button
              key={next}
              className="is-quiet"
              onClick={() => {
                setMode(next);
                setError("");
                setMessage("");
              }}
            >
              {LABELS[next]}
            </button>
          ))}
      </div>

      <p className="gate-fineprint">
        강의 자료는 로그인하고 승인받은 사람에게만 열립니다. <Link to="/privacy">개인정보처리방침</Link>
      </p>
    </main>
  );
}

/** 가입은 됐지만 아직 승인 전. 서버가 403 `pending_approval`을 줄 때 나온다. */
export function PendingApproval({ email, onSignOut }: { email: string; onSignOut: () => void }) {
  return (
    <main className="gate">
      <h1>Study_EZ</h1>
      <p className="gate-note">
        <strong>{email}</strong> 으로 가입되었습니다.
        <br />
        관리자 승인 뒤에 자료가 보입니다.
      </p>
      <button className="is-quiet" onClick={onSignOut}>
        로그아웃
      </button>
    </main>
  );
}
