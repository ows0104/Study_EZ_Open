import { Suspense, lazy, useEffect, useState } from "react";
import { BrowserRouter, Link, Route, Routes, useLocation } from "react-router-dom";
import { AuthProvider, LoginPage, PendingApproval, useAuth } from "./auth";
import { CalendarPage } from "./calendar/CalendarPage";
import { getMe, resetFirstScreen, startFirstScreen } from "./firstScreen";
import type { Me } from "./types";

/**
 * 캘린더만 첫 번들에 둔다.
 *
 * 나머지 셋은 착륙 화면이 아니다 — 관리는 관리자만, 개인정보처리방침은 심사팀과
 * 가끔 누르는 사람만, 강의 상세는 캘린더에서 새 창으로 연다. 앱 코드 전체가
 * 40KB뿐이라 여기서 빠지는 것은 20KB 남짓이고, **이 조각들이 따로 오는 값은
 * 왕복 한 번이다.** 지금 그 왕복이 비싼 곳(LAX)에서 오고 있어서 이득이 크지
 * 않다 — PoP가 제자리로 오면 그대로 이득만 남는다.
 */
const LecturePage = lazy(() => import("./lecture/LecturePage").then((m) => ({ default: m.LecturePage })));
const AdminPage = lazy(() => import("./admin/AdminPage").then((m) => ({ default: m.AdminPage })));
const PrivacyPage = lazy(() => import("./PrivacyPage").then((m) => ({ default: m.PrivacyPage })));

const Loading = <p className="notice">불러오는 중…</p>;

function Shell() {
  const { loading, session, email, signOut } = useAuth();
  const location = useLocation();
  const [me, setMe] = useState<Me | null>(null);
  const [meError, setMeError] = useState("");

  useEffect(() => {
    if (!session) {
      // 같은 탭에서 다음 사람이 로그인할 수 있다. 앞사람 것을 들고 있지 않는다.
      resetFirstScreen();
      setMe(null);
      return;
    }
    // `me`만 기다리지 않는다 — 시간표도 여기서 같이 나간다. 아래에서 `me`가
    // 올 때까지 캘린더를 마운트하지 않으므로, 미리 안 띄우면 두 왕복이 줄을 선다.
    startFirstScreen();
    getMe()
      .then(setMe)
      .catch((cause: Error) => setMeError(cause.message));
  }, [session]);

  // 개인정보처리방침은 로그인이나 관리자 승인 없이 심사팀과 사용자 모두가
  // 항상 열 수 있어야 한다. Hook 호출 뒤에 갈라야 경로 전환 때 호출 순서도 같다.
  if (location.pathname === "/privacy")
    return (
      <Suspense fallback={Loading}>
        <PrivacyPage />
      </Suspense>
    );

  if (loading) return Loading;
  // 개인정보처리방침을 제외한 자료 화면은 로그인 뒤에만 열린다.
  if (!session) return <LoginPage />;
  if (meError) return <p className="notice is-error">{meError}</p>;
  if (!me) return Loading;
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
        <Suspense fallback={Loading}>
          <Routes>
            <Route path="/" element={<CalendarPage />} />
            <Route path="/lectures/:subject/:runId" element={<LecturePage />} />
            <Route
              path="/admin"
              element={me.isAdmin ? <AdminPage /> : <p className="notice">관리자만 쓸 수 있습니다.</p>}
            />
            <Route path="*" element={<p className="notice">없는 화면입니다.</p>} />
          </Routes>
        </Suspense>
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
