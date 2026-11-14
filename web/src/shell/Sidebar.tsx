import { useEffect, useRef, useState, type ReactNode } from "react";
import { Link, NavLink, useNavigate } from "react-router-dom";
import { FeedbackButton } from "../feedback/FeedbackButton";
import { Icon } from "./icons";
import { useFlagPreference } from "../preferences";

/**
 * 좌측 메뉴(2026-11 개편). 위에서부터 학습 · 커뮤니티 · 도움 · 프로필.
 *
 * 아직 없는 화면(통합 퀴즈·오류 토의·진탐 공유·결제)은 기능이 생길 때까지 넣지 않는다
 * (2026-11-06 사용자 결정). 자유 노트는 서버 저장과 함께 열었다(2026-11-07). 관리는 관리자에게만 보인다. 접으면 아이콘만 남고, 접힘은 이 기기에 남긴다.
 */
const KEY = "studyez-sidebar";

type Item = { to: string; label: string; icon: () => ReactNode; end?: boolean; dot?: boolean };

function Nav({ item, collapsed }: { item: Item; collapsed: boolean }) {
  return (
    <NavLink
      to={item.to}
      end={item.end}
      className={({ isActive }) => `nav-item${isActive ? " is-current" : ""}`}
      title={collapsed ? item.label : undefined}
    >
      <span className="nav-icon">
        <item.icon />
        {item.dot ? <i className="nav-dot" aria-label="새 공지" /> : null}
      </span>
      <span className="nav-label">{item.label}</span>
    </NavLink>
  );
}

export function Sidebar({ email, isAdmin, unseenNotice, onSignOut }: {
  email: string;
  isAdmin: boolean;
  unseenNotice: boolean;
  onSignOut: () => void;
}) {
  const [collapsed, setCollapsed] = useFlagPreference(KEY);
  const [menu, setMenu] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();

  // 메뉴 밖을 누르거나 Esc면 프로필 메뉴를 닫는다.
  useEffect(() => {
    if (!menu) return;
    const onDown = (ev: MouseEvent) => {
      if (!menuRef.current?.contains(ev.target as Node)) setMenu(false);
    };
    const onKey = (ev: KeyboardEvent) => {
      if (ev.key === "Escape") setMenu(false);
    };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [menu]);

  const study: Item[] = [
    { to: "/", label: "캘린더", icon: Icon.calendar, end: true },
    { to: "/study", label: "강의 목록", icon: Icon.list },
    { to: "/notes", label: "자유 노트", icon: Icon.note },
  ];
  const community: Item[] = [{ to: "/notices", label: "공지사항", icon: Icon.bell, dot: unseenNotice }];
  const initials = (email.split("@")[0] || "?").slice(0, 2);

  return (
    <aside className={`sidebar${collapsed ? " is-collapsed" : ""}`} aria-label="주 메뉴">
      <div className="sidebar-head">
        <Link className="sidebar-brand" to="/" title="Study_EZ 홈">Study_EZ</Link>
        <button
          type="button"
          className="icon-button sidebar-toggle"
          onClick={() => setCollapsed(!collapsed)}
          aria-label={collapsed ? "메뉴 펼치기" : "메뉴 접기"}
          title={collapsed ? "메뉴 펼치기" : "메뉴 접기"}
        >
          <Icon.panel />
        </button>
      </div>

      <nav className="sidebar-scroll">
        <div className="nav-group">
          <div className="nav-group-title">학습</div>
          {study.map(item => <Nav key={item.to} item={item} collapsed={collapsed} />)}
        </div>
        <div className="nav-group">
          <div className="nav-group-title">커뮤니티</div>
          {community.map(item => <Nav key={item.to} item={item} collapsed={collapsed} />)}
        </div>
      </nav>

      <div className="sidebar-foot">
        <Nav item={{ to: "/guide", label: "이용방법", icon: Icon.help }} collapsed={collapsed} />
        <FeedbackButton
          launch={{
            className: "nav-item",
            title: collapsed ? "문의하기" : undefined,
            content: <><span className="nav-icon"><Icon.mail /></span><span className="nav-label">문의하기</span></>,
          }}
        />
        {isAdmin ? <Nav item={{ to: "/admin", label: "관리", icon: Icon.shield }} collapsed={collapsed} /> : null}
        <div className="profile-wrap" ref={menuRef}>
          <button
            type="button"
            className="profile"
            onClick={() => setMenu(v => !v)}
            aria-expanded={menu}
            aria-haspopup="menu"
            title={collapsed ? email : undefined}
          >
            <span className="avatar" aria-hidden="true">{initials}</span>
            <span className="profile-text">
              <strong>{email.split("@")[0]}</strong>
              <small>{email}</small>
            </span>
            <span className="profile-caret"><Icon.upDown /></span>
          </button>
          {menu ? (
            <div className="profile-menu" role="menu">
              <div className="profile-menu-head">{email}</div>
              <button type="button" role="menuitem" onClick={() => { setMenu(false); navigate("/settings"); }}>
                <Icon.settings /> 설정
              </button>
              <hr />
              <button type="button" role="menuitem" onClick={() => { setMenu(false); onSignOut(); }}>
                <Icon.logout /> 로그아웃
              </button>
            </div>
          ) : null}
        </div>
      </div>
    </aside>
  );
}
