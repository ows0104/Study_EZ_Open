import { useEffect, useState } from "react";
import { BrowserRouter, Link, Route, Routes, useLocation } from "react-router-dom";
import { api } from "./api";
import { AuthProvider, LoginPage, PendingApproval, useAuth } from "./auth";
import { CalendarPage } from "./calendar/CalendarPage";
import { LecturePage } from "./lecture/LecturePage";
import { AdminPage } from "./admin/AdminPage";
import { PrivacyPage } from "./PrivacyPage";
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

  // 개인정보처리방침은 로그인이나 관리자 승인 없이 심사팀과 사용자 모두가
  // 항상 열 수 있어야 한다. Hook 호출 뒤에 갈라야 경로 전환 때 호출 순서도 같다.
  if (location.pathname === "/privacy") return <PrivacyPage />;

  if (loading) return <p className="notice">불러오는 중…</p>;
  // 개인정보처리방침을 제외한 자료 화면은 로그인 뒤에만 열린다.
  if (!session) return <LoginPage />;
  if (meError) return <p className="notice is-error">{meError}</p>;
  if (!me) return <p className="notice">불러오는 중…</p>;
  // 가입은 됐지만 아직 승인 전. 자료를 부르는 화면으로 보내지 않는다.
  if (!me.isApproved) return <PendingApproval email={me.email || email} onSignOut={signOut} />;

  // 강의 상세는 새 창으로 열린다. 그 창에는 네비게이션이 없는 편이 낫다 —
  // 자료를 보러 온 창이고, 돌아갈 캘린더는 원래 창에 그대로 있다.
  const bare = location.pathname.startsWith("/lectures/");
  // 캘린더는 격자다. 읽기 좋은 폭으로 가둘 이유가 없고, 패널이 340px을 가져가는
  // 만큼 가로가 곧 요일 칸의 폭이 된다. 글을 읽는 화면들만 좁게 둔다.
  const wide = location.pathname === "/";

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
      <main className={`app-main${bare ? " is-bare" : ""}${wide ? " is-wide" : ""}`}>
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
