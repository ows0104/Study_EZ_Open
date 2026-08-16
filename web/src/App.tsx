import { BrowserRouter, Link, Route, Routes, useLocation } from "react-router-dom";
import { AuthProvider, LoginPage, useAuth } from "./auth";
import { CalendarPage } from "./calendar/CalendarPage";
import { LecturePage } from "./lecture/LecturePage";
import { AdminPage } from "./admin/AdminPage";

function Shell() {
  const { loading, session, email, signOut } = useAuth();
  const location = useLocation();

  if (loading) return <p className="notice">불러오는 중…</p>;
  // 로그인 없이 열리는 화면은 없다. 자료가 제3자 저작물이므로 우회로를 두지 않는다.
  if (!session) return <LoginPage />;

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
          <nav>
            <Link to="/admin">관리</Link>
          </nav>
          <span className="app-user">
            {email}
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
          <Route path="/admin" element={<AdminPage />} />
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
