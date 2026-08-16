import { useEffect, useState } from "react";
import { BrowserRouter, Link, Route, Routes, useLocation } from "react-router-dom";
import { api } from "./api";
import { AuthProvider, LoginPage, PendingApproval, useAuth } from "./auth";
import { CalendarPage } from "./calendar/CalendarPage";
import { LecturePage } from "./lecture/LecturePage";
import { AdminPage } from "./admin/AdminPage";
import type { Me } from "./types";

function Shell() {
  const { loading, session, email, signOut } = useAuth();
  const location = useLocation();
  const [me, setMe] = useState<Me | null>(null);
  const [meError, setMeError] = useState("");

  useEffect(() => {
    if (!session) {
      setMe(null);
      return;
    }
    api<Me>("/api/me")
      .then(setMe)
      .catch((cause: Error) => setMeError(cause.message));
  }, [session]);

  if (loading) return <p className="notice">불러오는 중…</p>;
  // 로그인 없이 열리는 화면은 없다.
  if (!session) return <LoginPage />;
  if (meError) return <p className="notice is-error">{meError}</p>;
  if (!me) return <p className="notice">불러오는 중…</p>;
  // 가입은 됐지만 아직 승인 전. 자료를 부르는 화면으로 보내지 않는다.
  if (!me.isApproved) return <PendingApproval email={me.email || email} onSignOut={signOut} />;

  // 강의 상세는 새 창으로 열린다. 그 창에는 네비게이션이 없는 편이 낫다 —
  // 자료를 보러 온 창이고, 돌아갈 캘린더는 원래 창에 그대로 있다.
  const bare = location.pathname.startsWith("/lectures/");

  return (
    <>
      {bare ? null : (
        <header className="app-bar">
          <Link className="app-brand" to="/">
            Study_EZ
          </Link>
          <nav>{me.isAdmin ? <Link to="/admin">관리</Link> : null}</nav>
          <span className="app-user">
            {me.email || email}
            <button className="is-quiet" onClick={signOut}>
              로그아웃
            </button>
          </span>
        </header>
      )}
      <main className={bare ? "app-main is-bare" : "app-main"}>
        <Routes>
          <Route path="/" element={<CalendarPage />} />
          <Route path="/lectures/:subject/:runId" element={<LecturePage />} />
          <Route
            path="/admin"
            element={me.isAdmin ? <AdminPage /> : <p className="notice">관리자만 쓸 수 있습니다.</p>}
          />
          <Route path="*" element={<p className="notice">없는 화면입니다.</p>} />
        </Routes>
      </main>
    </>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Shell />
      </BrowserRouter>
    </AuthProvider>
  );
}
