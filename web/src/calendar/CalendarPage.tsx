import { lazy, Suspense, useCallback, useMemo } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "../api";
import { useBankLink } from "../bank/bankBridge";
import { bumpPreviewVersion, usePreviewLink } from "../bridge/previewBridge";
import { previewProviders, type PreviewProvider } from "../types/lectures";
import { CalendarGrid } from "./CalendarGrid";
import { EventChip } from "./EventChip";
import { displayInfo } from "./kinds";
import { useCalendarTimetable } from "./useCalendarTimetable";
import { useTodayPlan } from "./useTodayPlan";
import type { ExamPlan } from "../types/studyPlan";
import {
  addDays,
  calendarRange,
  prequizDone,
  startOfWeek,
  studyDayKey,
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
  // 주간만 보여 준다(2026-11-07 사용자 지시: 월간·주/월 전환·오늘 버튼 없음, 날짜 줄 양끝 화살표로 넘긴다).
  const mode: CalendarMode = "week";
  const savedDate = params.get("date") ?? "";
  const parsedDate = /^\d{4}-\d{2}-\d{2}$/.test(savedDate) ? new Date(`${savedDate}T12:00:00`) : new Date();
  const anchorDate = Number.isNaN(parsedDate.getTime()) ? new Date() : parsedDate;
  // 회독·학습률은 늘 보인다(2026-11 개편, 토글 없음). 첫 화면 요청은 그대로 두고 그린 뒤 이어 받는다.
  const showLearning = true;
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
  const setAnchorDate = (value: Date) => remember("date", toDateKey(value));
  const setOpened = (value: CalendarEntry | null) => remember("event", value?.id ?? null);
  // 덱 모아받기 보기는 관리자에게도 없앴다(2026-11-07 사용자 지시). 강의 패널 「관리자」의 블럭 덱 받기는 남는다.

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
  const { plan: todayPlan, loading: planLoading } = useTodayPlan();

  const weekStart = startOfWeek(anchorDate);
  const weekEnd = addDays(weekStart, 4);
  const span = `${weekStart.getMonth() + 1}.${weekStart.getDate()} – ${weekEnd.getMonth() + 1}.${weekEnd.getDate()}`;

  // 머리 줄의 하루는 한국시간 새벽 4시에 바뀐다(2026-11-10 사용자 지시, 학습일과 같은 기준).
  // 「내일 예습」: 내일 날짜 강의 중 예습 퀴즈를 아직 끝내지 않은 것. 실습은 시험에 안 나와 세지 않는다(2026-11-11 사용자 지시).
  const now = new Date();
  const todayKey = studyDayKey(now);
  const tomorrowKey = studyDayKey(new Date(now.getTime() + 86_400_000));
  const tomorrowLectures = entries
    .filter(e => e.date === tomorrowKey && info.get(e.id)?.kind !== "practice") // CBL·TBL도 category는 practice라 kind로 가른다
    .flatMap(e => e.lectures);
  const preLoading = tomorrowLectures.some(l => l.studyLoaded === false);
  // 강의 하나 = 막대 한 칸. 예습 퀴즈가 올라온 강의만 센다.
  const preSlots = tomorrowLectures.filter(l => l.marks.prequiz).map(l => prequizDone(l));
  const preTomorrow = preSlots.filter(done => !done).length;
  const exam = nextExam(entries, events ?? [], todayKey);

  function step(direction: -1 | 1) {
    setAnchorDate(addDays(anchorDate, 7 * direction));
  }

  if (error && !events) return <p className="notice is-error" role="alert">{error}{" "}<button onClick={reload}>다시 시도</button></p>;
  if (!events) return <p className="notice">시간표를 불러오는 중…</p>;

  return (
    /* 패널이 열리면 캘린더가 왼쪽으로 좁아진다. 덮지 않으므로 패널을 연 채로
       다른 칸을 눌러 갈아탈 수 있다. */
    <div className={`calendar-page ${opened ? "is-split" : ""}`}>
      <div className="calendar-main">
        <header className="calendar-head">
          <h1>
            <span className="calendar-title">{blockWeek(entries, info, weekStart) || span}</span>
            {exam ? <span className="calendar-dday" title={`${exam.label} · ${exam.dateLabel}`}>{exam.days === 0 ? "D-day" : `D-${exam.days}`}</span> : null}
          </h1>
          {/* 내일 강의의 예습·오늘 복습. 머리 오른쪽 끝, 좁은 화면에서는 아래 줄(2026-11-07 사용자 지시).
              C안(2026-11-11): 남은 양을 크게, 한 양은 아래 막대로. 다 하면 칸이 회색으로 가라앉는다. */}
          <div className="today-board" aria-label="오늘 할 일">
            <PreCard loading={preLoading} slots={preSlots} remaining={preTomorrow} />
            <ReviewCard loading={planLoading} plan={todayPlan} />
          </div>
        </header>
        {learningLoading ? <span className="sr-only" role="status">표시된 기간의 학습률을 불러오는 중…</span> : null}
        {error || learningError ? <p className="notice is-error" role="alert">{error || learningError}{" "}<button onClick={reload}>다시 시도</button></p> : null}

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
          onStep={step}
        />

        <div className="calendar-legend">
          <span><i className="legend-swatch is-lecture" /> 강의·실습·TBL·CBL</span>
          <span><i className="legend-swatch is-exam" /> 시험</span>
          <span className="legend-sep" />
          <span><span className="readline"><i className="rl-pre is-on" /></span> 예습 퀴즈 완료</span>
          <span><span className="readline"><i className="rl-pre" /></span> 미완료</span>
          <span className="legend-meter"><span className="meter"><span style={{ width: "25%" }} /></span> 복습 학습률</span>
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

/** 「내일 예습」: 남은 강의 수, 강의마다 한 칸짜리 막대. */
function PreCard({ loading, slots, remaining }: { loading: boolean; slots: boolean[]; remaining: number }) {
  const done = !loading && slots.length > 0 && remaining === 0;
  return (
    <span className={`today-card is-pre ${done ? "is-done" : ""}`}>
      <span className="today-card-row">
        <span className="today-card-label">내일 예습</span>
        <b>{loading ? "…" : done ? <>✓ {slots.length}<small>강의</small></> : <>{remaining}<small>강의</small></>}</b>
      </span>
      {!loading && slots.length ? (
        <span className="today-card-bar is-split" role="img" aria-label={`내일 예습 ${slots.length - remaining}/${slots.length}강의`}>
          {slots.map((filled, index) => <i key={index} className={filled ? "is-filled" : ""} />)}
        </span>
      ) : null}
    </span>
  );
}

/** 「오늘 복습」: 시험 대비 오늘 확보 목표(%p) 중 남은 양, 막대는 진행률.
 *  푼 문제 = 그 시험 강의들의 오늘(새벽 4시 기준) Main-Quiz 평가 수 `reviewedToday`(2026-11-13 사용자 지시).
 *  하루 목표를 문제 수로 환산하는 일은 docs/changes/2026-11-13-daily-goal-questions/handoff.md. */
function ReviewCard({ loading, plan }: { loading: boolean; plan: ExamPlan | null }) {
  const done = Boolean(plan?.met);
  return (
    <span className={`today-card is-review ${done ? "is-done" : ""}`}>
      <span className="today-card-row">
        <span className="today-card-label">오늘 복습{plan ? <small className="today-card-solved">푼 문제 {plan.reviewedToday.toLocaleString("ko-KR")}</small> : null}</span>
        <b>{loading && !plan ? "…" : !plan ? "–"
          : done ? <>✓ {plan.requiredGain.toFixed(1)}<small>%p</small></>
          : <>{plan.remainingGain.toFixed(1)}<small>%p</small></>}</b>
      </span>
      {plan ? (
        <span className="today-card-bar" role="progressbar" aria-label="오늘 복습 목표" aria-valuemin={0} aria-valuemax={100} aria-valuenow={plan.progressPercent}>
          <i className="is-filled" style={{ width: `${plan.progressPercent}%` }} />
        </span>
      ) : null}
    </span>
  );
}
