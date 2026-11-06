import { lazy, Suspense, useCallback, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "../api";
import { useBankLink } from "../bank/bankBridge";
import { BundleButton } from "../bundle/BundleButton";
import { decksIn, useBundleDecks } from "../bundle/decks";
import { bumpPreviewVersion, usePreviewLink } from "../bridge/previewBridge";
import { previewProviders, type PreviewProvider } from "../types/lectures";
import { useMe } from "../useMe";
import { CalendarGrid } from "./CalendarGrid";
import { EventChip } from "./EventChip";
import { displayInfo } from "./kinds";
import { useCalendarTimetable } from "./useCalendarTimetable";
import { useTodayDue } from "./useTodayDue";
import {
  addDays,
  calendarRange,
  prequizDone,
  startOfWeek,
  toDateKey,
  toCalendarEntries,
  weekDayLabels,
  type CalendarEntry,
  type CalendarMode,
} from "./entries";

const EventPanel = lazy(() => import("./EventPanel").then(m => ({ default: m.EventPanel })));

/**
 * 캘린더가 홈이다.
 *
 * 시간표만으로 완성된 화면이고, 파이프라인 산출물은 나중에 점으로 붙는다.
 * 그래서 첫 배포에 강의 자료가 하나도 없어도 쓸모가 있다.
 */
export function CalendarPage() {
  const [params, setParams] = useSearchParams();
  const mode: CalendarMode = params.get("view") === "month" ? "month" : "week";
  const savedDate = params.get("date") ?? "";
  const parsedDate = /^\d{4}-\d{2}-\d{2}$/.test(savedDate) ? new Date(`${savedDate}T12:00:00`) : new Date();
  const anchorDate = Number.isNaN(parsedDate.getTime()) ? new Date() : parsedDate;
  // 회독·학습률은 늘 보인다(2026-11 개편, 토글 없음). 첫 화면 요청은 그대로 두고 그린 뒤 이어 받는다.
  const showLearning = true;
  const [showBundles, setShowBundles] = useState(false);
  const range = calendarRange(anchorDate, mode);
  const { events, error, learningError, learningLoading, reload } = useCalendarTimetable(range.start, range.end, showLearning);
  // 방문 기록에 날짜·보기·열린 패널을 남겨 퀴즈에서 뒤로 와도 같은 자리로 돌아온다.
  function remember(name: string, value: string | null) {
    setParams(current => {
      const next = new URLSearchParams(current);
      if (value === null) next.delete(name);
      else next.set(name, value);
      return next;
    }, { replace: true });
  }
  const setMode = (value: CalendarMode) => remember("view", value);
  const setAnchorDate = (value: Date) => remember("date", toDateKey(value));
  const setOpened = (value: CalendarEntry | null) => remember("event", value?.id ?? null);
  // 자리 둘이 무엇을 세는지가 이것으로 갈린다. 칸마다 묻지 않고 여기서 한 번
  // 묻는다 — `useMe`는 훅이라 칸 안에서 부르면 강의 수만큼 붙는다.
  const isAdmin = Boolean(useMe()?.isAdmin);
  /**
   * 덱이 어디 있고 무엇을 받아 갔나. **여기 한 곳에서만 부른다** — 날짜 머리
   * 다섯과 열려 있는 패널이 같은 값을 봐야 하고, 칸마다 훅을 걸면 강의 수만큼
   * 요청이 붙는다(`isAdmin` 을 여기서 한 번 묻는 것과 같은 이유다).
   */
  const bundles = useBundleDecks(isAdmin && showBundles && mode === "week", new URLSearchParams(range).toString());

  /**
   * 확장이 만들어 준 예습 링크를 받아 저장한다. 종류에 따라 주인이 다르다.
   *
   *   chatgpt(`/c/`)       → 내 개인 링크. 누구나 저장된다
   *   chatgpt_share(`/share/`) → 반 공통 기본 링크. **관리자만** 성공한다
   *
   * 공유는 기본 링크를 만들 때만 생기므로(확장이 개인 모드에서는 감시를 안 건다)
   * 두 번째 갈래가 개인 예습으로 도는 일은 없다. 그래도 일반 사용자가 어쩌다
   * 보내게 되면 403을 받고 조용히 지나간다 — 대화 자체는 이미 열렸으므로 그
   * 사람에게는 아무것도 실패하지 않았다.
   */
  // Quiz Bank 답 본문도 같은 자리에서 받는다(관리자). 확장이 이 탭으로 밀어 준다.
  useBankLink();
  usePreviewLink(
    useCallback(async ({ lectureId, kind, url }) => {
      const [subject, runId] = lectureId.split("/");
      if (!subject || !runId) return;
      const path = `${encodeURIComponent(subject)}/${encodeURIComponent(runId)}`;
      const shared = kind.endsWith("_share");
      const review = kind.endsWith("_review");
      const provider = (shared ? kind.slice(0, -6) : review ? kind.slice(0, -7) : kind) as PreviewProvider;
      if (!previewProviders.includes(provider)) return;
      if (shared) {
        await api(`/api/admin/lectures/${path}/preview`, {
          method: "PUT",
          body: JSON.stringify({ provider, shareUrl: url }),
        });
      } else {
        await api(`/api/lectures/${path}/${review ? "my-review" : "my-preview"}`, {
          method: "PUT",
          body: JSON.stringify({ provider, conversationUrl: url }),
        });
      }
      // 칸의 점(marks)과 열려 있는 패널을 둘 다 갱신한다. 시간표만 다시 부르면
      // 패널은 자기가 부른 강의 상세를 그대로 들고 있어서 안 바뀐다.
      bumpPreviewVersion();
      reload();
    }, [reload]),
  );

  const entries = useMemo(() => toCalendarEntries(events ?? []), [events]);
  const info = useMemo(() => displayInfo(events ?? []), [events]);
  const opened = entries.find(entry => entry.id === params.get("event")) ?? null;
  const todayDue = useTodayDue(events);

  const heading = `${anchorDate.getFullYear()}년 ${anchorDate.getMonth() + 1}월`;
  const weekStart = startOfWeek(anchorDate);
  const weekEnd = addDays(weekStart, 4);
  const span = `${weekStart.getMonth() + 1}.${weekStart.getDate()} – ${weekEnd.getMonth() + 1}.${weekEnd.getDate()}`;
  const subheading = mode === "week" ? [blockWeek(entries, info, weekStart), span].filter(Boolean).join(" · ") : "평일만 표시";

  // 「오늘」 줄: 오늘 날짜에 배정된 강의 중 예습 퀴즈를 아직 끝내지 않은 것(사용자 지시: 오늘 배정된 양만).
  const todayKey = toDateKey(new Date());
  const todayLectures = entries.filter(e => e.date === todayKey).flatMap(e => e.lectures);
  const preLoading = todayLectures.some(l => l.studyLoaded === false);
  const preToday = todayLectures.filter(l => l.marks.prequiz && !prequizDone(l)).length;
  const exam = nextExam(entries, events ?? [], todayKey);

  function step(direction: -1 | 1) {
    setAnchorDate(
      mode === "week"
        ? addDays(anchorDate, 7 * direction)
        : new Date(anchorDate.getFullYear(), anchorDate.getMonth() + direction, 1),
    );
  }

  if (error && !events) return <p className="notice is-error" role="alert">{error}{" "}<button onClick={reload}>다시 시도</button></p>;
  if (!events) return <p className="notice">시간표를 불러오는 중…</p>;

  return (
    /* 패널이 열리면 캘린더가 왼쪽으로 좁아진다. 덮지 않으므로 패널을 연 채로
       다른 칸을 눌러 갈아탈 수 있다. */
    <div className={`calendar-page ${opened ? "is-split" : ""}`}>
      <div className="calendar-main">
        <header className="page-head calendar-head">
          <div>
            <h1>{heading}</h1>
            <p className="page-sub">{subheading}</p>
          </div>
          {exam ? (
            <div className="dday" title={exam.entry.title}>
              <span className="dday-label">
                <b>{exam.label}</b>
                {exam.dateLabel}
              </span>
              <strong>{exam.days === 0 ? "D-day" : `D-${exam.days}`}</strong>
            </div>
          ) : null}
        </header>

        <div className="today-strip">
          <span className="today-label">오늘</span>
          <span className="today-pill is-pre">미열람 예습 <b>{preLoading ? "…" : `${preToday}강의`}</b></span>
          <span className="today-pill is-review">미열람 복습 퀴즈 <b>{todayDue === null ? "…" : `${todayDue}문제`}</b></span>
          <span className="today-spacer" />
          {isAdmin && mode === "week" ? (
            <button className="is-quiet" aria-pressed={showBundles} onClick={() => setShowBundles(old => !old)}>
              덱 모아받기 {showBundles ? "접기" : "보기"}
            </button>
          ) : null}
          <button className="pill-button" onClick={() => setAnchorDate(new Date())}>오늘</button>
          <span className="calendar-stepper">
            <button className="icon-button" onClick={() => step(-1)} aria-label="이전">‹</button>
            <button className="icon-button" onClick={() => step(1)} aria-label="다음">›</button>
          </span>
          <div className="calendar-mode" role="group" aria-label="보기 전환">
            <button className={mode === "week" ? "is-selected" : ""} aria-pressed={mode === "week"} onClick={() => setMode("week")}>주</button>
            <button className={mode === "month" ? "is-selected" : ""} aria-pressed={mode === "month"} onClick={() => setMode("month")}>월</button>
          </div>
        </div>
        {learningLoading ? <span className="sr-only" role="status">표시된 기간의 학습률을 불러오는 중…</span> : null}
        {showBundles && mode === "week" && !bundles.decks && !bundles.error ? <span className="sr-only" role="status">표시된 기간의 덱 목록을 불러오는 중…</span> : null}
        {error || learningError || bundles.error ? <p className="notice is-error" role="alert">{error || learningError || bundles.error}{" "}<button onClick={() => { reload(); bundles.reload(); }}>다시 시도</button></p> : null}

        <CalendarGrid
          mode={mode}
          anchorDate={anchorDate}
          entries={entries}
          renderEntry={(entry, compact) => (
            <EventChip
              key={entry.id}
              entry={entry}
              info={info.get(entry.id)}
              compact={compact}
              onOpen={setOpened}
              active={opened?.id === entry.id}
              showLearning={showLearning}
            />
          )}
          /* 격자 맨 아랫줄의 하루치 모아받기. 예습과 복습을 갈라 둔다 — 쓰는
             때가 다르고(강의 전 · 강의 후) 덱 나무도 이미 갈라져 있다. 덱이
             없는 날에는 `BundleButton` 이 스스로 아무것도 안 그린다. */
          renderDay={isAdmin && showBundles ? (dateKey) => {
            if (!isAdmin) return null;
            const all = bundles.decks;
            if (!all) return null;
            const scope = { kind: "day", date: dateKey } as const;
            return (
              <span className="day-bundles">
                {(["pre", "main"] as const).map((kind) => (
                  <BundleButton
                    key={kind}
                    compact
                    scope={scope}
                    kind={kind}
                    decks={decksIn(all, scope, kind)}
                    onDone={bundles.reload}
                  />
                ))}
              </span>
            );
          } : undefined}
        />

        <div className="calendar-legend">
          <span><i className="legend-swatch is-lecture" /> 강의·실습·TBL·CBL</span>
          <span><i className="legend-swatch is-exam" /> 시험</span>
          {mode === "week" ? (
            <>
              <span className="legend-sep" />
              <span><span className="readline"><i className="rl-pre is-on" /></span> 예습 퀴즈</span>
              <span className="legend-meter"><span className="meter"><span style={{ width: "25%", background: "color-mix(in srgb, var(--accent) 85%, var(--surface))" }} /></span> 복습 학습률</span>
            </>
          ) : null}
        </div>
      </div>

      {/* key로 칸이 바뀔 때 패널 안의 상태(고른 강의·불러온 자료)를 갈아 끼운다. */}
      {opened ? (
        <Suspense fallback={<aside className="event-panel"><p role="status">강의 자료를 불러오는 중…</p><button onClick={() => setOpened(null)}>닫기</button></aside>}><EventPanel
          key={opened.id}
          entry={opened}
          info={info.get(opened.id)}
          onClose={() => setOpened(null)}
        /></Suspense>
      ) : null}

    </div>
  );
}

/** 그 주에 가장 많이 든 블럭과 블럭 안의 주차(「감염과 면역 1차 1주차」). */
function blockWeek(entries: CalendarEntry[], info: ReturnType<typeof displayInfo>, weekStart: Date) {
  const startKey = toDateKey(weekStart);
  const endKey = toDateKey(addDays(weekStart, 4));
  const counts = new Map<string, number>();
  for (const e of entries) {
    const block = info.get(e.id)?.block;
    if (block && e.date >= startKey && e.date <= endKey) counts.set(block, (counts.get(block) ?? 0) + 1);
  }
  const block = [...counts.entries()].sort((a, b) => b[1] - a[1])[0]?.[0];
  if (!block) return "";
  const first = entries.find(e => info.get(e.id)?.block === block);
  if (!first) return block;
  const firstWeek = startOfWeek(new Date(`${first.date}T12:00:00`));
  const n = Math.round((weekStart.getTime() - firstWeek.getTime()) / (7 * 86_400_000)) + 1;
  return `${block} ${n}주차`;
}

/** 오늘 이후 가장 가까운 시험. 세부에 「(1차)」가 있으면 「1차 시험」. */
function nextExam(entries: CalendarEntry[], events: { id: string; details: string }[], todayKey: string) {
  const entry = entries.find(e => e.category === "exam" && e.date >= todayKey);
  if (!entry) return null;
  const date = new Date(`${entry.date}T12:00:00`);
  const today = new Date(`${todayKey}T12:00:00`);
  const days = Math.round((date.getTime() - today.getTime()) / 86_400_000);
  const raw = events.find(e => e.id === entry.id)?.details ?? entry.detail;
  const order = `${entry.title} ${raw}`.match(/(\d+)\s*차/);
  const day = weekDayLabels[(date.getDay() + 6) % 7] ?? "";
  return {
    entry,
    days,
    label: order ? `${order[1]}차 시험` : "시험",
    dateLabel: `${date.getMonth() + 1}월 ${date.getDate()}일${day ? ` (${day})` : ""}`,
  };
}
