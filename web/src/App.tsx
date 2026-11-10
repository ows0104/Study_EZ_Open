import { Suspense, lazy, useCallback, useEffect, useState } from "react";
import { BrowserRouter, Navigate, Route, Routes, useLocation } from "react-router-dom";
import { api } from "./api";
import { AuthProvider, LoginPage, PendingApproval, useAuth } from "./auth";
import { CalendarPage } from "./calendar/CalendarPage";
import { getMe, resetFirstScreen, startFirstScreen } from "./firstScreen";
import { seenNotice } from "./notices/seen";
import { Sidebar } from "./shell/Sidebar";
import { StudyNav } from "./StudyNav";
import { StudyChrome, isMainQuizPath } from "./shell/studyChrome";
import type { Me } from "./types/account";
import type { Notice } from "./types/notices";

/**
 * 캘린더만 첫 번들에 둔다.
 *
 * 나머지 넷은 착륙 화면이 아니다 — 관리는 관리자만, 개인정보처리방침은 심사팀과
 * 가끔 누르는 사람만, 강의 상세와 Pre-Quiz는 캘린더에서 같은 탭으로 연다. 앱 코드
 * 전체가 40KB뿐이라 여기서 빠지는 것은 20KB 남짓이고, **이 조각들이 따로 오는
 * 값은 왕복 한 번이다.** 지금 그 왕복이 비싼 곳(LAX)에서 오고 있어서 이득이 크지
 * 않다 — PoP가 제자리로 오면 그대로 이득만 남는다.
 */
const LecturePage = lazy(() => import("./lecture/LecturePage").then((m) => ({ default: m.LecturePage })));
const QuizPage = lazy(() => import("./lecture/QuizPage").then((m) => ({ default: m.QuizPage })));
// Quiz Bank 풀이 화면. 같은 탭에서 강의·캘린더와 오간다.
const BankStudyPage = lazy(() => import("./bank/BankStudy").then((m) => ({ default: m.BankStudyPage })));
const RootLearningPage = lazy(() => import("./bank/RootLearning").then((m) => ({ default: m.RootLearningPage })));
const ConnectionLearningPage = lazy(() => import("./bank/ConnectionLearning").then((m) => ({ default: m.ConnectionLearningPage })));
const BankCatalogPage = lazy(() => import("./bank/BankCatalog").then((m) => ({ default: m.BankCatalogPage })));
const BankBatchPage = lazy(() => import("./bank/BankBatch").then((m) => ({ default: m.BankBatchPage })));
const AdminPage = lazy(() => import("./admin/AdminPage").then((m) => ({ default: m.AdminPage })));
const PrivacyPage = lazy(() => import("./PrivacyPage").then((m) => ({ default: m.PrivacyPage })));
// 공지·이용방법(2026-10-04). 둘 다 가끔 여는 글이라 첫 번들에 안 싣는다.
const NoticesPage = lazy(() => import("./notices/NoticesPage").then((m) => ({ default: m.NoticesPage })));
const GuidePage = lazy(() => import("./notices/GuidePage").then((m) => ({ default: m.GuidePage })));
const SettingsPage = lazy(() => import("./settings/SettingsPage").then((m) => ({ default: m.SettingsPage })));
const NotesPage = lazy(() => import("./notes/NotesPage").then((m) => ({ default: m.NotesPage })));

const Loading = <p className="notice">불러오는 중…</p>;

function Shell() {
  const { loading, session, email, signOut } = useAuth();
  const location = useLocation();
  const [me, setMe] = useState<Me | null>(null);
  const [meError, setMeError] = useState("");
  // 이 브라우저가 아직 안 본 공지가 있는가 — 좌측 메뉴 「공지사항」 옆의 점.
  const [unseenNotice, setUnseenNotice] = useState(false);
  const onNoticeSeen = useCallback(() => setUnseenNotice(false), []);
  // Main-Quiz 화면이 지금 문항을 푸는가. 시작 화면은 홈처럼 좌측 메뉴 안에 둔다.
  const [quizSolving, setQuizSolving] = useState(false);

  useEffect(() => {
    if (!session) {
      // 같은 탭에서 다음 사람이 로그인할 수 있다. 앞사람 것을 들고 있지 않는다.
      resetFirstScreen();
      setMe(null);
      return;
    }
    // `me`만 기다리지 않는다 — 시간표도 여기서 같이 나간다. 아래에서 `me`가
    // 올 때까지 캘린더를 마운트하지 않으므로, 미리 안 띄우면 두 왕복이 줄을 선다.
    startFirstScreen(location.pathname === "/");
    getMe()
      .then(setMe)
      .catch((cause: Error) => setMeError(cause.message));
  }, [session]);

  // **첫 화면을 기다리게 하지 않는다.** 캘린더가 `me` 와 시간표를 받고 선 뒤에
  // 따로 묻는다. 실패해도 점이 안 찍힐 뿐이다.
  const approved = Boolean(me?.isApproved);
  useEffect(() => {
    if (!approved) return;
    api<Notice[]>("/api/notices")
      .then((rows) => setUnseenNotice(rows.some((row) => row.id > seenNotice())))
      .catch(() => {});
  }, [approved]);

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

  // 학습 화면은 넓은 본문과 간단한 이동 메뉴를 사용한다.
  const mainQuiz = isMainQuizPath(location.pathname);
  const bare = (mainQuiz && quizSolving) || (!mainQuiz && (
    location.pathname.startsWith("/lectures/") ||
    location.pathname.startsWith("/mainquiz/") ||
    location.pathname.startsWith("/legacy-mainquiz/") ||
    location.pathname.startsWith("/bank/")));
  // 캘린더는 격자다. 읽기 좋은 폭으로 가둘 이유가 없고, 패널이 340px을 가져가는
  // 만큼 가로가 곧 요일 칸의 폭이 된다. 글을 읽는 화면들만 좁게 둔다.
  const wide = location.pathname === "/" || location.pathname === "/study";
  // **푸는 창은 글 읽는 폭이 아니다.** 안키의 복습 화면처럼 창 전체를 카드로
  // 쓴다 — 문항·답·슬라이드가 다 이 폭을 쓰고, 답 버튼은 아래에 못 박힌다.
  // 문항 중앙값 43자·답 63자라 넓혀도 대개 한두 줄이고, 슬라이드는 원본이
  // 1152~1536px이라 700px 안에서는 절반으로 누웠다.
  const solving = bare && !location.pathname.startsWith("/lectures/");

  // 2026-11 개편: 상단 머리줄 대신 좌측 메뉴. 풀이 화면(bare)은 좌측 메뉴 없이 간단한 이동 줄만 둔다.
  return (
    <div className={`app-shell${bare ? " is-bare" : ""}`}>
      {bare ? null : (
        <Sidebar email={me.email || email} isAdmin={me.isAdmin} unseenNotice={unseenNotice} onSignOut={signOut} />
      )}
      <div className="app-column">
      {bare ? <StudyNav /> : null}
        <main
        className={`app-main${bare ? " is-bare" : ""}${wide ? " is-wide" : ""}${
          solving ? " is-solving" : ""
        }${location.pathname === "/notes" ? " is-notes" : ""
        }`}
      >
        <StudyChrome.Provider value={setQuizSolving}>
        <Suspense fallback={Loading}>
          <Routes>
            <Route path="/" element={<CalendarPage />} />
            <Route path="/study" element={<BankBatchPage />} />
            <Route path="/mastery" element={<Navigate to="/study" replace />} />
            <Route path="/lectures/:subject/:runId" element={<LecturePage />} />
            {/* 예습·복습은 같은 탭 안에서 서로 다른 주소로 이동한다. */}
            <Route path="/notices" element={<NoticesPage isAdmin={me.isAdmin} onSeen={onNoticeSeen} />} />
            <Route path="/guide" element={<GuidePage />} />
            <Route path="/notes" element={<NotesPage />} />
            <Route path="/settings" element={<SettingsPage email={me.email || email} onSignOut={signOut} />} />
            <Route path="/prequiz/:subject/:runId" element={<QuizPage kind="pre" />} />
            <Route path="/mainquiz/:subject/:runId" element={<BankStudyPage />} />
            <Route path="/legacy-mainquiz/:subject/:runId" element={<QuizPage kind="main" />} />
            <Route path="/bank/:subject/:runId" element={<BankStudyPage />} />
            <Route path="/bank/:subject/:runId/roots" element={<RootLearningPage />} />
            <Route path="/bank/:subject/:runId/connections" element={<ConnectionLearningPage />} />
            <Route path="/bank/:subject/:runId/all" element={<BankCatalogPage />} />
            {/* 관리 화면은 탭을 갈래로 들고 있다(`/admin/match` 등). 그 갈래는
                안에서 고르므로 여기서는 통째로 넘긴다. */}
            <Route
              path="/admin/*"
              element={me.isAdmin ? <AdminPage /> : <p className="notice">관리자만 쓸 수 있습니다.</p>}
            />
            <Route path="*" element={<p className="notice">없는 화면입니다.</p>} />
          </Routes>
        </Suspense>
        </StudyChrome.Provider>
        </main>
      </div>
    </div>
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
