import { StrictMode, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { createRoot } from 'react-dom/client';
import { Icon } from './icons';
import { ThemeTuner } from './theme';
import { NotesPage } from './notes';
import { useNoteReads } from './store';
import {
  addDays,
  BLOCKS,
  blockEntries,
  BLOCK1,
  BLOCK2,
  CURRENT,
  entriesBetween,
  startOfWeek,
  toKey,
  TODAY,
  weekdayLabels,
  type Cards,
  type Entry,
} from './data';
import './prototype.css';

/* ───────────────────────── 메뉴 ───────────────────────── */

type PageId =
  | 'calendar'
  | 'lectures'
  | 'combined'
  | 'notes'
  | 'notices'
  | 'errors'
  | 'share'
  | 'guide'
  | 'billing'
  | 'settings'
  | 'admin'
  | 'contact';

type NavItem = { id: PageId; label: string; icon: () => ReactNode; badge?: string; dot?: boolean };

/** 학습 현황·강의 모아풀기는 「강의 목록」 하나로 합쳤다(2026-11-05 사용자 지시). */
const STUDY: NavItem[] = [
  { id: 'calendar', label: '캘린더', icon: Icon.calendar },
  { id: 'lectures', label: '강의 목록', icon: Icon.list },
  { id: 'combined', label: '통합 퀴즈', icon: Icon.target },
  { id: 'notes', label: '자유 노트', icon: Icon.note },
];
const COMMUNITY: NavItem[] = [
  { id: 'notices', label: '공지사항', icon: Icon.bell, dot: true },
  { id: 'errors', label: '오류 토의', icon: Icon.message, badge: '3' },
  { id: 'share', label: '진탐 공유', icon: Icon.users },
];
/** 하단 도움 줄. 프로필·설정·결제는 프로필 메뉴가, 관리는 관리자에게만 보인다. */
const HELP: NavItem[] = [
  { id: 'guide', label: '이용방법', icon: Icon.help },
  { id: 'contact', label: '문의하기', icon: Icon.mail },
];
const ADMIN: NavItem = { id: 'admin', label: '관리', icon: Icon.shield };
const PROFILE_PAGES: NavItem[] = [
  { id: 'billing', label: '결제·이용권', icon: Icon.card },
  { id: 'settings', label: '프로필·설정', icon: Icon.settings },
];
const ALL = [...STUDY, ...COMMUNITY, ...HELP, ADMIN, ...PROFILE_PAGES];

function NavButton({ item, active, collapsed, onSelect }: { item: NavItem; active: boolean; collapsed: boolean; onSelect: (id: PageId) => void }) {
  return (
    <button
      className={`nav-item${active ? ' is-active' : ''}`}
      onClick={() => onSelect(item.id)}
      title={collapsed ? item.label : undefined}
      aria-current={active ? 'page' : undefined}
    >
      <span className="nav-icon">
        <item.icon />
        {item.dot ? <i className="nav-dot" aria-label="새 글" /> : null}
      </span>
      <span className="nav-label">{item.label}</span>
      {item.badge ? <span className="nav-badge">{item.badge}</span> : null}
    </button>
  );
}

function Sidebar({ page, onSelect, collapsed, onToggle, isAdmin }: { page: PageId; onSelect: (id: PageId) => void; collapsed: boolean; onToggle: () => void; isAdmin: boolean }) {
  const [menu, setMenu] = useState(false);
  const group = (title: string, items: NavItem[]) => (
    <div className="nav-group">
      <div className="nav-group-title">{title}</div>
      {items.map((item) => (
        <NavButton key={item.id} item={item} active={page === item.id} collapsed={collapsed} onSelect={onSelect} />
      ))}
    </div>
  );
  return (
    <aside className={`sidebar${collapsed ? ' is-collapsed' : ''}`} aria-label="주 메뉴">
      <div className="sidebar-head">
        <button className="brand" onClick={() => onSelect('calendar')} title="Study_EZ 홈">
          <span className="brand-name">Study_EZ</span>
        </button>
        <button className="icon-button sidebar-toggle" onClick={onToggle} aria-label={collapsed ? '메뉴 펼치기' : '메뉴 접기'} title={collapsed ? '메뉴 펼치기' : '메뉴 접기'}>
          <Icon.panel />
        </button>
      </div>

      <nav className="sidebar-scroll">
        {group('학습', STUDY)}
        {group('커뮤니티', COMMUNITY)}
      </nav>

      <div className="sidebar-foot">
        {(isAdmin ? [...HELP, ADMIN] : HELP).map((item) => (
          <NavButton key={item.id} item={item} active={page === item.id} collapsed={collapsed} onSelect={onSelect} />
        ))}
        <div className="profile-wrap">
          <button className={`profile${page === 'settings' || page === 'billing' ? ' is-active' : ''}`} onClick={() => setMenu((v) => !v)} aria-expanded={menu} title={collapsed ? '박지민 · 본과 1학년' : undefined}>
            <span className="avatar">지민</span>
            <span className="profile-text">
              <strong>박지민</strong>
              <small>본과 1학년 · 이용권 사용 중</small>
            </span>
            <span className="profile-caret"><Icon.upDown /></span>
          </button>
          {menu ? (
            <div className="profile-menu" role="menu">
              <div className="profile-menu-head">student@studyez.kr</div>
              <button role="menuitem" onClick={() => { onSelect('settings'); setMenu(false); }}><Icon.settings /> 프로필·설정</button>
              <button role="menuitem" onClick={() => { onSelect('billing'); setMenu(false); }}><Icon.card /> 결제·이용권</button>
              <hr />
              <button role="menuitem" onClick={() => setMenu(false)}><Icon.logout /> 로그아웃</button>
            </div>
          ) : null}
        </div>
      </div>
    </aside>
  );
}

/* ───────────────────────── 공용: 번호·회독·학습률 ───────────────────────── */

const NUMBERED = new Set(['lecture', 'practice', 'tbl', 'cbl']);
const learnable = (e: Entry) => e.preTotal !== null;
const nowMinutes = TODAY.getHours() * 60 + TODAY.getMinutes();
const ended = (e: Entry) => e.date < toKey(TODAY) || (e.date === toKey(TODAY) && minutes(e.end) <= nowMinutes);
/** 아직 끝나지 않은 강의인데 예습 퀴즈를 끝내지 않았다 */
const needsPre = (e: Entry) => learnable(e) && !ended(e) && !e.preDone;

/** 시트·목록에 쓰는 긴 번호표 */
function fullCode(e: Entry) {
  if (e.category === 'lecture') return `강의 ${e.no}`;
  if (e.category === 'exam') return `${e.no}차 시험`;
  if (e.category === 'intro') return '다른 과목';
  return e.code;
}

/**
 * 교수 옆 표시(2026-11-05 사용자 지시). 작년과 같은 교수면 아무것도 없다.
 * 두 자리 연도 = 작년과 다르지만 최근 5년 안에 맡은 가장 최근 해, N = 최근 5년 담당 기록 없음(New).
 */
function ProfTag({ note }: { note: string | null }) {
  if (!note) return null;
  const isNew = note === 'N';
  const text = isNew ? '작년과 다른 교수 · 보유한 최근 5년 자료에 담당 기록 없음' : `작년과 다른 교수 · 20${note}년에 담당`;
  return <span className={`prof-tag${isNew ? ' is-new' : ''}`} title={text} aria-label={text}>{note}</span>;
}

/** 강의 아래 한 줄: 교수(+변경 표시) · 분야. 날짜·시각은 넣지 않는다(2026-11-05 사용자 지시). */
function Byline({ e }: { e: Entry }) {
  if (!e.professor && !e.subject) return null;
  return (
    <>
      {e.professor}
      <ProfTag note={e.profNote} />
      {e.professor && e.subject ? ' · ' : ''}
      {e.subject}
    </>
  );
}
const hasByline = (e: Entry) => Boolean(e.professor || e.subject);

function minutes(time: string) {
  const [h, m] = time.split(':').map(Number);
  return h * 60 + m;
}

/**
 * 회독 줄(2026-11-05 사용자 지시). 학습률 막대와 같은 두께의 점선으로, 막대 위에 옅게 둔다.
 *   첫 토막 = 예습 퀴즈. 1회독까지만 세고, 끝까지 풀었을 때만 채운다.
 *   뒤 토막 = 강의록 회독(자가 기록) 하나에 하나.
 */
function ReadLine({ entry, size }: { entry: Entry; size?: 'lg' }) {
  const { count } = useNoteReads();
  if (!learnable(entry)) return null;
  const notes = count(entry);
  const label = `예습 퀴즈 ${entry.preDone ? '완료' : '미완료'} · 강의록 ${notes}회독`;
  return (
    <span className={`readline${size ? ` is-${size}` : ''}`} title={label} aria-label={label}>
      <i className={`rl-pre${entry.preDone ? ' is-on' : ''}`} />
      {notes ? (
        <span className="rl-notes">
          {Array.from({ length: Math.min(notes, 6) }, (_, i) => <i key={i} className="rl-note" />)}
        </span>
      ) : null}
    </span>
  );
}

/**
 * 복습 학습률 막대. 덜 공부한 강의가 더 눈에 띄게, 채울수록 옅어진다(2026-11-05 사용자 지시).
 * 0%여도 막대는 있다. 아직 열리지 않은 강의는 회색 바탕만 그린다.
 */
function Meter({ value }: { value: number | null }) {
  if (value === null) return <span className="meter is-closed" title="강의가 끝나면 복습이 열립니다" />;
  const strength = Math.round(100 - Math.min(1, Math.max(0, value)) * 62);
  return (
    <span className="meter" title={`복습 학습률 ${Math.round(value * 100)}%`}>
      <span style={{ width: `${Math.max(value, 0) * 100}%`, background: `color-mix(in srgb, var(--accent) ${strength}%, #fff)` }} />
    </span>
  );
}

/* ───────────────────────── 캘린더 ───────────────────────── */

const HOURS = [9, 10, 11, 12, 13, 14, 15, 16];
/** 점심(12시)은 늘 비어 있어 얇게 둔다. */
const LUNCH_HOUR = 12;
const LUNCH_HEIGHT = 26;
const hourHeight = (hour: number, row: number) => (hour === LUNCH_HOUR ? LUNCH_HEIGHT : row);

/** 시각(분) → 격자 맨 위에서의 거리. 점심 줄만 높이가 달라 시간마다 더한다. */
function yAt(mins: number, row: number) {
  let y = 0;
  for (const h of HOURS) {
    const height = hourHeight(h, row);
    if (mins < (h + 1) * 60) return y + (Math.max(0, mins - h * 60) / 60) * height;
    y += height;
  }
  return y;
}
/** 한 시간 높이. 화면 높이를 다 쓰도록 재되, 너무 낮거나 높지 않게 묶는다. */
function useRowHeight() {
  const ref = useRef<HTMLDivElement>(null);
  const [row, setRow] = useState(64);
  useEffect(() => {
    const el = ref.current?.parentElement;
    if (!el) return;
    const measure = () => setRow(Math.max(60, Math.min(96, Math.floor((el.clientHeight - 54 - LUNCH_HEIGHT) / (HOURS.length - 1)))));
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return [ref, row] as const;
}

function Chip({ entry, active, compact, showLearning, onOpen }: { entry: Entry; active: boolean; compact?: boolean; showLearning: boolean; onOpen: (e: Entry) => void }) {
  const todo = needsPre(entry);
  return (
    <button
      className={`chip is-${entry.category}${active ? ' is-open' : ''}${compact ? ' is-compact' : ''}${todo ? ' is-todo' : ''}`}
      onClick={() => onOpen(entry)}
      title={`${fullCode(entry)} · ${entry.title}`}
    >
      <span className="chip-title">
        {NUMBERED.has(entry.category) ? <span className="chip-code">{entry.code}</span> : null}
        {entry.title}
      </span>
      {!compact && hasByline(entry) ? <span className="chip-meta"><Byline e={entry} /></span> : null}
      {!compact && showLearning && learnable(entry) ? (
        <span className="chip-learning">
          <ReadLine entry={entry} />
          <Meter value={entry.review} />
        </span>
      ) : null}
    </button>
  );
}

function WeekGrid({ anchor, entries, openId, showLearning, onOpen }: { anchor: Date; entries: Entry[]; openId: string | null; showLearning: boolean; onOpen: (e: Entry) => void }) {
  const start = startOfWeek(anchor);
  const days = Array.from({ length: 5 }, (_, i) => addDays(start, i));
  const todayKey = toKey(TODAY);
  const [ref, ROW] = useRowHeight();
  const nowTop = yAt(nowMinutes, ROW);
  const gridHeight = yAt((HOURS[HOURS.length - 1] + 1) * 60, ROW);
  return (
    <div className="week" ref={ref}>
      <div className="week-head">
        <div className="week-gutter" />
        {days.map((d, i) => {
          const key = toKey(d);
          return (
            <div key={key} className={`week-day${key === todayKey ? ' is-today' : ''}${key < todayKey ? ' is-past' : ''}`}>
              <span className="week-dow">{weekdayLabels[i]}</span>
              <span className="week-date">{d.getDate()}</span>
            </div>
          );
        })}
      </div>
      <div className="week-body">
        <div className="week-gutter">
          {HOURS.map((h) => (
            <div key={h} className={`week-hour${h === LUNCH_HOUR ? ' is-lunch' : ''}`} style={{ height: hourHeight(h, ROW) }}><span>{h === LUNCH_HOUR ? '점심' : `${h}:00`}</span></div>
          ))}
        </div>
        {days.map((d) => {
          const key = toKey(d);
          const dayEntries = entries.filter((e) => e.date === key);
          return (
            <div key={key} className={`week-col${key === todayKey ? ' is-today' : ''}`}>
              {HOURS.map((h) => <div key={h} className={`week-cell${h === LUNCH_HOUR ? ' is-lunch' : ''}`} style={{ height: hourHeight(h, ROW) }} />)}
              {dayEntries.map((e) => {
                const top = yAt(minutes(e.start), ROW);
                // 끝 시각은 50분이라 다음 정시까지 채워서 칸 사이 간격을 일정하게 둔다.
                const height = yAt(minutes(e.end) + 10, ROW) - top;
                return (
                  <div key={e.id} className="week-event" style={{ top, height }}>
                    <Chip entry={e} active={openId === e.id} showLearning={showLearning} onOpen={onOpen} />
                  </div>
                );
              })}
              {key === todayKey && nowTop > 0 && nowTop < gridHeight ? (
                <div className="now-line" style={{ top: nowTop }} aria-label="지금" />
              ) : null}
            </div>
          );
        })}
      </div>
    </div>
  );
}

/** 그 달의 평일이 든 주만. 1일이 주말이면 다음 월요일 주부터 센다. */
function monthWeeks(anchor: Date) {
  const first = new Date(anchor.getFullYear(), anchor.getMonth(), 1, 12);
  const last = new Date(anchor.getFullYear(), anchor.getMonth() + 1, 0, 12);
  const firstWeekday = first.getDay() === 0 ? addDays(first, 1) : first.getDay() === 6 ? addDays(first, 2) : first;
  const start = startOfWeek(firstWeekday);
  const weeks = Math.floor((startOfWeek(last).getTime() - start.getTime()) / (7 * 86400000)) + 1;
  return [start, weeks] as const;
}

function MonthGrid({ anchor, entries, openId, onOpen }: { anchor: Date; entries: Entry[]; openId: string | null; onOpen: (e: Entry) => void }) {
  const [gridStart, weeks] = monthWeeks(anchor);
  const days = Array.from({ length: weeks * 5 }, (_, i) => addDays(gridStart, Math.floor(i / 5) * 7 + (i % 5)));
  const todayKey = toKey(TODAY);
  return (
    <div className="month">
      {weekdayLabels.map((d) => <div key={d} className="month-dow">{d}</div>)}
      {days.map((d) => {
        const key = toKey(d);
        const list = entries.filter((e) => e.date === key);
        const shown = list.slice(0, 4);
        return (
          <div key={key} className={`month-cell${d.getMonth() !== anchor.getMonth() ? ' is-outside' : ''}${key === todayKey ? ' is-today' : ''}`}>
            <span className="month-date">{d.getDate()}</span>
            <div className="month-list">
              {shown.map((e) => <Chip key={e.id} entry={e} compact active={openId === e.id} showLearning={false} onOpen={onOpen} />)}
              {list.length > shown.length ? <span className="month-more">+{list.length - shown.length}개</span> : null}
            </div>
          </div>
        );
      })}
    </div>
  );
}

/* ───────────────────────── 카드 단계 막대 ───────────────────────── */

/**
 * 운영 Quiz Bank와 같은 네 단계(web/src/bank/StudyOverview.tsx). 「기억 유지」는 「저장」으로 부른다(2026-11-05 사용자 지시).
 * 색은 미열람(위기) → 인지 → 인출 → 저장(안심) 순으로 따뜻한 색에서 차분한 색으로 간다.
 */
const STAGES = [
  { key: 'unseen', label: '미열람' },
  { key: 'recognized', label: '인지' },
  { key: 'retrieving', label: '인출' },
  { key: 'retained', label: '저장' },
] as const;

function sumCards(list: Entry[]): Cards {
  const out: Cards = { total: 0, unseen: 0, recognized: 0, retrieving: 0, retained: 0, due: 0 };
  for (const e of list) {
    if (!e.cards) continue;
    for (const k of Object.keys(out) as (keyof Cards)[]) out[k] += e.cards[k];
  }
  return out;
}

function StageSummary({ cards }: { cards: Cards }) {
  return (
    <div className="stage-card">
      <div className="stage-legend">
        {STAGES.map((s) => (
          <span key={s.key}><i className={`stage-dot stage-${s.key}`} />{s.label}<b className={`stage-text-${s.key}`}>{cards[s.key].toLocaleString('ko-KR')}</b></span>
        ))}
      </div>
      <div className="stage-bar" role="img" aria-label={STAGES.map((s) => `${s.label} ${cards[s.key]}장`).join(' · ')}>
        {STAGES.map((s) => (cards[s.key] > 0 ? <span key={s.key} className={`stage-${s.key}`} style={{ flex: cards[s.key] }} /> : null))}
      </div>
    </div>
  );
}

/* ───────────────────────── 강의 상세(오른쪽 시트) ───────────────────────── */

/** 학습률 25% 구간 색(2026-11-05 사용자 지시). 낮을수록 위기 색, 높을수록 안심 색 — 카드 단계 색과 같은 줄기 */
function rateBand(rate: number | null) {
  if (rate === null) return 'is-closed';
  if (rate < 0.25) return 'is-band1';
  if (rate < 0.5) return 'is-band2';
  if (rate < 0.75) return 'is-band3';
  return 'is-band4';
}

/**
 * 강의록 회독 기록 줄. 첫 토막은 예습 퀴즈(끝냈을 때만), 뒤는 강의록 회독, 끝에 +.
 * 지우기: 강의록 토막에 마우스를 올리면 그 토막이 빨갛게 바뀌고, 누르면 지운다. 바로 아래에 「되돌리기」가 잠깐 뜬다.
 */
function ReadEditor({ entry }: { entry: Entry }) {
  const { count, change } = useNoteReads();
  const notes = count(entry);
  const [undo, setUndo] = useState(false);
  useEffect(() => {
    if (!undo) return;
    const t = setTimeout(() => setUndo(false), 4000);
    return () => clearTimeout(t);
  }, [undo]);
  return (
    <div className="read-editor">
      <span className="readline is-lg">
        {entry.preDone ? <i className="rl-pre is-on" title="예습 퀴즈" /> : null}
        {Array.from({ length: notes }, (_, i) => (
          <button key={i} className="rl-note is-button" title="지우기" aria-label={`강의록 회독 ${i + 1} 지우기`} onClick={() => { change(entry, -1); setUndo(true); }} />
        ))}
      </span>
      <button className="read-plus" onClick={() => change(entry, 1)} aria-label="강의록 회독 추가" title="회독 추가"><Icon.plus /></button>
      {undo ? <button className="read-undo" onClick={() => { change(entry, 1); setUndo(false); }}>되돌리기</button> : null}
    </div>
  );
}

function EventSheet({ entry, onClose }: { entry: Entry; onClose: () => void }) {
  const group = entry.category === 'tbl' || entry.category === 'cbl';
  const cards = entry.cards;
  const open = entry.review !== null;
  return (
    <aside className="sheet" aria-label="강의 상세">
      <div className="sheet-top">
        <span className="sheet-tags">
          <span className={`tag is-${entry.category}`}>{fullCode(entry)}</span>
          {entry.category !== 'intro' ? <span className="tag is-quiet">{entry.block}</span> : null}
        </span>
        <button className="icon-button" onClick={onClose} aria-label="닫기"><Icon.x /></button>
      </div>
      <h2 className="sheet-title">{entry.title}</h2>
      {entry.professor ? (
        <p className="sheet-prof">
          <span>{group ? '분반' : '교수'}</span>
          {entry.professor}
          <ProfTag note={entry.profNote} />
        </p>
      ) : null}

      {learnable(entry) ? (
        <>
          <section className="sheet-block">
            <h3><i className="role-dot is-pre" />예습</h3>
            <div className="sheet-actions">
              <button className="action-button"><Icon.external />공통 대화</button>
              <button className="action-button"><Icon.external />개인 대화</button>
              <button className="action-button is-quiz is-pre"><Icon.play />예습 퀴즈</button>
            </div>
          </section>

          <section className="sheet-block">
            <h3><i className="role-dot is-review" />복습</h3>
            <div className="sheet-actions">
              <button className="action-button" disabled={!open}><Icon.external />개인 대화</button>
              <button className="action-button is-quiz is-review" disabled={!open}>
                <Icon.play />복습 퀴즈{open && cards?.due ? <b>{cards.due}</b> : null}
              </button>
            </div>
          </section>

          <section className="sheet-block sheet-stats">
            <h3>통계</h3>
            <div className="stat-row">
              <span className="stat-label">회독</span>
              <ReadEditor entry={entry} />
            </div>
            <div className="stat-row">
              <span className="stat-label">학습률</span>
              <div className="stat-rate">
                <b className={`rate-text ${rateBand(entry.review)}`}>{open ? `${Math.round((entry.review ?? 0) * 100)}%` : '0%'}</b>
                <Meter value={entry.review} />
              </div>
            </div>
            {cards ? (
              <div className="stat-row is-top">
                <span className="stat-label">카드</span>
                <div className="stat-stages">
                  <StageSummary cards={cards} />
                </div>
              </div>
            ) : null}
          </section>

          <div className="sheet-foot">
            <span className="deck-links">
              <Icon.download />덱 다운로드
              <button>예습</button>
              <button disabled={!open}>복습</button>
            </span>
            <span className="today-spacer" />
            <button className="ghost-button"><Icon.message /> 오류 토의 <span className="count">2</span></button>
            <button className="ghost-button"><Icon.flag /> 제보</button>
          </div>
        </>
      ) : null}
    </aside>
  );
}

function useEscape(fn: () => void) {
  useEffect(() => {
    const onKey = (ev: KeyboardEvent) => {
      if (ev.key === 'Escape') fn();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [fn]);
}

/** 시험까지 남은 날. 다음 시험이 없으면 null */
function nextExam() {
  const exams = entriesBetween(TODAY, addDays(TODAY, 60)).filter((e) => e.category === 'exam');
  const exam = exams[0];
  if (!exam) return null;
  const days = Math.round((Date.parse(`${exam.date}T12:00:00`) - Date.parse(`${toKey(TODAY)}T12:00:00`)) / 86400000);
  return { exam, days };
}

/** 그 주가 속한 블럭과 블럭 안의 주차. 시간표 밖이면 null */
function blockWeekOf(weekStart: Date) {
  const key = toKey(weekStart);
  if (key < '2026-11-02' || key > '2026-11-27') return null;
  const [name, start] = key >= '2026-11-23' ? [BLOCK2, '2026-11-23'] : [BLOCK1, '2026-11-02'];
  const week = Math.round((weekStart.getTime() - new Date(`${start}T12:00:00`).getTime()) / (7 * 86400000)) + 1;
  return `${name} ${week}주차`;
}

function CalendarPage() {
  const [mode, setMode] = useState<'week' | 'month'>('week');
  const [anchor, setAnchor] = useState(TODAY);
  const [openId, setOpenId] = useState<string | null>(null);
  const close = useMemo(() => () => setOpenId(null), []);
  useEscape(close);

  const range = useMemo(() => {
    if (mode === 'week') {
      const s = startOfWeek(anchor);
      return [s, addDays(s, 4)] as const;
    }
    const [s, weeks] = monthWeeks(anchor);
    return [s, addDays(s, weeks * 7 - 1)] as const;
  }, [anchor, mode]);
  const entries = useMemo(() => entriesBetween(range[0], range[1]), [range]);
  const opened = entries.find((e) => e.id === openId) ?? null;

  const weekStart = startOfWeek(anchor);
  const blockWeek = blockWeekOf(weekStart);
  const title = `${anchor.getFullYear()}년 ${anchor.getMonth() + 1}월`;
  const span = `${weekStart.getMonth() + 1}.${weekStart.getDate()} – ${addDays(weekStart, 4).getMonth() + 1}.${addDays(weekStart, 4).getDate()}`;
  const sub = mode === 'week' ? (blockWeek ? `${blockWeek} · ${span}` : span) : '평일만 표시';

  const step = (dir: -1 | 1) =>
    setAnchor((a) => (mode === 'week' ? addDays(a, 7 * dir) : new Date(a.getFullYear(), a.getMonth() + dir, 1, 12)));

  // 「오늘」 줄은 오늘 배정된 양만 센다(2026-11-05 사용자 지시).
  const todays = entriesBetween(TODAY, TODAY);
  const preToday = todays.filter((e) => learnable(e) && !e.preDone).length;
  const reviewToday = sumCards(blockEntries(CURRENT.id)).due;
  const exam = nextExam();
  const examDate = exam ? new Date(`${exam.exam.date}T12:00:00`) : null;

  return (
    <div className={`calendar-layout${opened ? ' has-sheet' : ''}`}>
      <div className="calendar-main">
        <header className="page-head">
          <div>
            <h1>{title}</h1>
            <p className="page-sub">{sub}</p>
          </div>
          {exam && examDate ? (
            <div className="dday" title={exam.exam.title}>
              <span className="dday-label">
                <b>{exam.exam.no}차 시험</b>
                {examDate.getMonth() + 1}월 {examDate.getDate()}일 ({weekdayLabels[(examDate.getDay() + 6) % 7]})
              </span>
              <strong>D-{exam.days}</strong>
            </div>
          ) : null}
        </header>

        <div className="today-strip">
          <span className="today-label">오늘</span>
          <button className="chip-pill is-pre">미열람 예습 <b>{preToday}강의</b></button>
          <button className="chip-pill is-review">미열람 복습 퀴즈 <b>{reviewToday}문제</b></button>
          <span className="today-spacer" />
          <button className="pill-button" onClick={() => setAnchor(TODAY)}>오늘</button>
          <div className="stepper">
            <button className="icon-button" onClick={() => step(-1)} aria-label="이전"><Icon.left /></button>
            <button className="icon-button" onClick={() => step(1)} aria-label="다음"><Icon.right /></button>
          </div>
          <div className="segmented" role="group" aria-label="보기 전환">
            <button aria-pressed={mode === 'week'} onClick={() => setMode('week')}>주</button>
            <button aria-pressed={mode === 'month'} onClick={() => setMode('month')}>월</button>
          </div>
        </div>

        <div className="calendar-surface">
          {mode === 'week' ? (
            <WeekGrid anchor={anchor} entries={entries} openId={openId} showLearning onOpen={(e) => setOpenId(e.id)} />
          ) : (
            <MonthGrid anchor={anchor} entries={entries} openId={openId} onOpen={(e) => setOpenId(e.id)} />
          )}
        </div>

        <footer className="legend">
          <span><i className="swatch is-lecture" />강의·실습·TBL·CBL</span>
          <span><i className="swatch is-exam" />시험</span>
          <span><i className="swatch is-intro" />다른 과목</span>
          {mode === 'week' ? (
            <>
              <span className="legend-sep" />
              <span><span className="readline"><i className="rl-pre is-on" /></span>예습 퀴즈</span>
              <span><span className="readline"><span className="rl-notes"><i className="rl-note" /><i className="rl-note" /></span></span>강의록 회독</span>
              <span className="legend-meter"><span className="meter"><span style={{ width: '25%', background: 'color-mix(in srgb, var(--accent) 85%, #fff)' }} /></span>복습 학습률</span>
            </>
          ) : null}
        </footer>
      </div>
      {opened ? <EventSheet entry={opened} onClose={close} /> : null}
    </div>
  );
}

/* ───────────────────────── 강의 목록(학습 현황 + 모아풀기) ───────────────────────── */

function BlockPicker({ value, onChange }: { value: string; onChange: (id: string) => void }) {
  const [open, setOpen] = useState(false);
  const current = BLOCKS.find((b) => b.id === value)!;
  return (
    <div className="block-picker">
      <button className="pill-button block-picker-button" onClick={() => setOpen((v) => !v)} aria-expanded={open}>
        <span className="block-picker-label">블럭</span>
        {current.name}
        {current.current ? <span className="block-now">이번 블럭</span> : current.next ? <span className="block-now is-next">다음 블럭</span> : null}
        <Icon.chevronDown />
      </button>
      {open ? (
        <>
          <div className="nb-scrim" onClick={() => setOpen(false)} />
          <div className="block-menu" role="listbox">
            {BLOCKS.map((b) => (
              <button key={b.id} role="option" aria-selected={b.id === value} onClick={() => { onChange(b.id); setOpen(false); }}>
                <span className="block-menu-text">
                  <b>{b.name}{b.current ? <span className="block-now">이번 블럭</span> : b.next ? <span className="block-now is-next">다음 블럭</span> : null}</b>
                  <small>{b.range}</small>
                </span>
                {b.id === value ? <Icon.check /> : null}
              </button>
            ))}
          </div>
        </>
      ) : null}
    </div>
  );
}

/** 강의·실습·TBL/CBL을 처음부터 나눈다(2026-11-05 사용자 지시). 시험·다른 과목은 목록에 넣지 않는다. */
const SECTIONS: { id: string; label: string; match: (e: Entry) => boolean }[] = [
  { id: 'lecture', label: '강의', match: (e) => e.category === 'lecture' },
  { id: 'practice', label: '실습', match: (e) => e.category === 'practice' },
  { id: 'group', label: 'TBL·CBL', match: (e) => e.category === 'tbl' || e.category === 'cbl' },
];

const num = (n: number) => <span className={n ? '' : 'is-zero'}>{n.toLocaleString('ko-KR')}</span>;

function LecturesPage() {
  const [blockId, setBlockId] = useState(CURRENT.id);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [openId, setOpenId] = useState<string | null>(null);
  const close = useMemo(() => () => setOpenId(null), []);
  useEscape(close);

  const all = useMemo(() => blockEntries(blockId).filter((e) => e.category !== 'intro' && e.category !== 'exam'), [blockId]);
  const block = BLOCKS.find((b) => b.id === blockId)!;
  const opened = all.find((e) => e.id === openId) ?? null;
  // 위 막대는 복습이 열린 강의만 센다. 아직 안 열린 강의까지 넣으면 미열람(위기 색)이 늘 대부분을 덮는다.
  const openedList = all.filter((e) => e.review !== null);
  const cards = sumCards(openedList);
  const opened2 = all.filter((e) => e.review !== null);
  const avg = opened2.length ? Math.round((opened2.reduce((s, e) => s + (e.review ?? 0), 0) / opened2.length) * 100) : null;

  const toggle = (id: string) =>
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  const selectable = all.filter((e) => e.review !== null);
  const allPicked = selectable.length > 0 && selectable.every((e) => selected.has(e.id));
  const pickedDue = all.filter((e) => selected.has(e.id)).reduce((s, e) => s + (e.cards?.due ?? 0), 0);

  const changeBlock = (id: string) => {
    setBlockId(id);
    setSelected(new Set());
    setOpenId(null);
  };

  return (
    <div className={`calendar-layout${opened ? ' has-sheet' : ''}`}>
      <div className="list-main">
        <header className="page-head">
          <div>
            <h1>강의 목록</h1>
            <p className="page-sub">{block.name} · {block.range}</p>
          </div>
          <div className="page-tools">
            <BlockPicker value={blockId} onChange={changeBlock} />
          </div>
        </header>

        <div className="list-stats">
          <div><span>오늘 복습</span><b className="is-review">{cards.due}<small>장</small></b></div>
          <div><span>학습률 평균</span><b>{avg === null ? '—' : `${avg}%`}</b></div>
          <div><span>전체 카드</span><b>{cards.total.toLocaleString('ko-KR')}<small>장</small></b></div>
        </div>
        <StageSummary cards={cards} />

        <div className="list-table" role="table" aria-label="강의 목록">
          <div className="list-row is-head" role="row">
            <span>
              <button className="check" aria-pressed={allPicked} aria-label="열린 강의 모두 선택" title="열린 강의 모두 선택" onClick={() => setSelected(allPicked ? new Set() : new Set(selectable.map((e) => e.id)))}>
                {allPicked ? <Icon.check /> : null}
              </button>
            </span>
            <span>번호</span>
            <span>강의</span>
            <span className="is-num">전체</span>
            {STAGES.map((s) => <span key={s.key} className="is-num is-stage"><i className={`stage-dot stage-${s.key}`} />{s.label}</span>)}
            <span className="is-num">복습</span>
            <span className="is-num">학습률</span>
          </div>
          {SECTIONS.map((section) => {
            const list = all.filter(section.match);
            if (!list.length) return null;
            return (
              <div key={section.id} className="list-section" role="rowgroup">
                <div className="list-section-title">{section.label}<span>{list.length}</span></div>
                {list.map((e) => {
                  const c = e.cards;
                  const canPick = e.review !== null;
                  const rate = e.review;
                  return (
                    <div
                      key={e.id}
                      className={`list-row${openId === e.id ? ' is-open' : ''}${selected.has(e.id) ? ' is-picked' : ''}${e.cards && e.review === null ? ' is-closed' : ''}`}
                      role="row"
                      onClick={() => setOpenId(e.id)}
                    >
                      <span onClick={(ev) => ev.stopPropagation()}>
                        {canPick ? (
                          <button className="check" aria-pressed={selected.has(e.id)} aria-label={`${fullCode(e)} 모아풀기에 넣기`} onClick={() => toggle(e.id)}>
                            {selected.has(e.id) ? <Icon.check /> : null}
                          </button>
                        ) : null}
                      </span>
                      <span className="list-code">{e.code}</span>
                      <span className="list-title">
                        <strong>{e.title}</strong>
                        {hasByline(e) ? <small><Byline e={e} /></small> : null}
                      </span>
                      {c ? (
                        <>
                          <span className="is-num">{num(c.total)}</span>
                          {STAGES.map((s) => <span key={s.key} className={`is-num is-stage stage-text-${s.key}`}>{num(c[s.key])}</span>)}
                          <span className={`is-num list-due${c.due ? ' is-on' : ''}`}>{num(c.due)}</span>
                          <span className={`is-num rate-text ${rateBand(rate)}`}>
                            {rate === null ? '0%' : `${Math.round(rate * 100)}%`}
                          </span>
                        </>
                      ) : (
                        <span className="list-none">퀴즈 없음</span>
                      )}
                    </div>
                  );
                })}
              </div>
            );
          })}
        </div>

        {selected.size ? (
          <div className="pick-bar" role="region" aria-label="모아풀기">
            <span><b>{selected.size}개 강의</b> 선택 · 오늘 복습 {pickedDue}장</span>
            <span className="today-spacer" />
            <button className="ghost-button is-on-dark" onClick={() => setSelected(new Set())}>선택 해제</button>
            <button className="primary-button"><Icon.play /> 모아풀기</button>
          </div>
        ) : null}
      </div>
      {opened ? <EventSheet entry={opened} onClose={close} /> : null}
    </div>
  );
}

/* ───────────────────────── 다른 화면(맛보기) ───────────────────────── */

function CombinedPage() {
  return (
    <div className="page">
      <header className="page-head"><div><h1>통합 퀴즈</h1></div></header>
      <div className="hero">
        <h2>무엇을 섞어서 풀까요?</h2>
        <div className="hero-row">
          <button className="primary-button"><Icon.plus /> 새 통합 퀴즈</button>
          <div className="hero-input"><input placeholder="예: 1차 시험 범위 중 미생물학 틀린 문제" /><button className="icon-button is-round" aria-label="만들기"><Icon.right /></button></div>
        </div>
        <div className="hero-pills">
          {['이번 주 전체', '틀린 문제만', '1차 시험 범위', '같은 교수 기출', '연결 문항'].map((p) => <button key={p} className="chip-pill">{p}</button>)}
        </div>
      </div>
    </div>
  );
}

const PLACEHOLDER: Partial<Record<PageId, string>> = {
  notices: '공지 목록. 읽지 않은 공지는 메뉴에 점으로 표시됩니다.',
  errors: '문항 오류를 함께 토의하는 게시판. 강의 패널의 「오류 토의」와 연결됩니다.',
  share: '진탐 자료를 나누는 공간.',
  guide: '이용방법 안내.',
  billing: '이용권·결제 내역.',
  settings: '프로필, 알림, 화면 설정.',
  admin: '관리자 화면(관리자에게만 보임).',
  contact: '운영진에게 문의를 남깁니다.',
};

function Placeholder({ id }: { id: PageId }) {
  const item = ALL.find((n) => n.id === id)!;
  return (
    <div className="page">
      <header className="page-head"><div><h1>{item.label}</h1><p className="page-sub">{PLACEHOLDER[id]}</p></div></header>
      <div className="empty"><item.icon /><p>프로토타입에서는 메뉴 자리만 잡아 두었습니다.</p></div>
    </div>
  );
}

/* ───────────────────────── 앱 ───────────────────────── */

function loadPage(): PageId {
  const raw = localStorage.getItem('proto-page');
  return ALL.some((n) => n.id === raw) ? (raw as PageId) : 'calendar';
}

function App() {
  const [page, setPage] = useState<PageId>(loadPage);
  useEffect(() => localStorage.setItem('proto-page', page), [page]);
  const [collapsed, setCollapsed] = useState(() => localStorage.getItem('proto-sidebar') === '1');
  useEffect(() => localStorage.setItem('proto-sidebar', collapsed ? '1' : '0'), [collapsed]);
  // 프로토타입 전용: 관리자 화면 보기. 일반 사용자에게는 「관리」 메뉴가 없다.
  const [isAdmin, setIsAdmin] = useState(() => localStorage.getItem('proto-admin') === '1');
  useEffect(() => {
    localStorage.setItem('proto-admin', isAdmin ? '1' : '0');
    if (!isAdmin) setPage((p) => (p === 'admin' ? 'calendar' : p));
  }, [isAdmin]);
  return (
    <div className={`app${collapsed ? ' is-collapsed' : ''}`}>
      <Sidebar page={page} onSelect={setPage} collapsed={collapsed} onToggle={() => setCollapsed((v) => !v)} isAdmin={isAdmin} />
      <main className="content">
        {page === 'calendar' ? <CalendarPage />
          : page === 'lectures' ? <LecturesPage />
          : page === 'combined' ? <CombinedPage />
          : page === 'notes' ? <NotesPage />
          : <Placeholder id={page} />}
      </main>
      <ThemeTuner isAdmin={isAdmin} onAdminChange={setIsAdmin} />
    </div>
  );
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
