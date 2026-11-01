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
import { useCalendarTimetable } from "./useCalendarTimetable";
import {
  addDays,
  calendarRange,
  formatWeekTitle,
  startOfWeek,
  toDateKey,
  toCalendarEntries,
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
  const [showLearning, setShowLearning] = useState(false);
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
  const opened = entries.find(entry => entry.id === params.get("event")) ?? null;

  const heading =
    mode === "week"
      ? formatWeekTitle(startOfWeek(anchorDate))
      : `${anchorDate.getFullYear()}년 ${anchorDate.getMonth() + 1}월`;

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
        {/* 날짜가 가운데다. 좌우를 같은 폭으로 잡아 두어야 제목이 길어져도
            화살표가 흔들리지 않는다. */}
        <div className="calendar-toolbar">
          <div className="calendar-actions is-left">
            <button onClick={() => setAnchorDate(new Date())}>오늘</button>
          </div>
          <div className="calendar-heading">
            <button className="calendar-step" onClick={() => step(-1)} aria-label="이전">
              ‹
            </button>
            <h1>{heading}</h1>
            <button className="calendar-step" onClick={() => step(1)} aria-label="다음">
              ›
            </button>
          </div>
          <div className="calendar-actions is-right">
            <div className="calendar-mode" role="group" aria-label="보기 전환">
              <button
                className={mode === "week" ? "is-selected" : ""}
                aria-pressed={mode === "week"}
                onClick={() => setMode("week")}
              >
                주
              </button>
              <button
                className={mode === "month" ? "is-selected" : ""}
                aria-pressed={mode === "month"}
                onClick={() => setMode("month")}
              >
                월
              </button>
            </div>
          </div>
        </div>

        <div className="calendar-options">
          <button className="is-quiet" aria-pressed={showLearning} onClick={() => setShowLearning(old => !old)}>학습률 {showLearning ? "접기" : "보기"}</button>
          {isAdmin && mode === "week" ? <button className="is-quiet" aria-pressed={showBundles} onClick={() => setShowBundles(old => !old)}>덱 모아받기 {showBundles ? "접기" : "보기"}</button> : null}
          {learningLoading ? <span role="status">표시된 기간의 학습률을 불러오는 중…</span> : null}
          {showBundles && mode === "week" && !bundles.decks && !bundles.error ? <span role="status">표시된 기간의 덱 목록을 불러오는 중…</span> : null}
        </div>
        {error || learningError || bundles.error ? <p className="notice is-error" role="alert">{error || learningError || bundles.error}{" "}<button onClick={() => { reload(); bundles.reload(); }}>다시 시도</button></p> : null}

        <CalendarGrid
          mode={mode}
          anchorDate={anchorDate}
          entries={entries}
          renderEntry={(entry, compact) => (
            <EventChip
              key={entry.id}
              entry={entry}
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
          {showLearning ? <span className="legend-group is-learning" aria-label="학습률 표시 안내">
            <b>왼쪽 예습 · 오른쪽 복습</b>
            <span><i className="learning-legend-track is-empty" /> 0%: 테두리만</span>
            <span><i className="learning-legend-track is-progress" /> 진행 중</span>
            <span><i className="learning-legend-track is-complete" /> 100%</span>
            <span>빈칸: 퀴즈 없음</span>
          </span> : null}
          <span className="legend-group">
            <span>
              <i className="legend-swatch is-lecture" /> 강의
            </span>
            <span>
              <i className="legend-swatch is-practice" /> 실습
            </span>
            <span>
              <i className="legend-swatch is-exam" /> 시험
            </span>
            <span>
              <i className="legend-swatch is-off" /> 휴일·자율
            </span>
          </span>
        </div>
      </div>

      {/* key로 칸이 바뀔 때 패널 안의 상태(고른 강의·불러온 자료)를 갈아 끼운다. */}
      {opened ? (
        <Suspense fallback={<aside className="event-panel"><p role="status">강의 자료를 불러오는 중…</p><button onClick={() => setOpened(null)}>닫기</button></aside>}><EventPanel
          key={opened.id}
          entry={opened}
          onClose={() => setOpened(null)}
        /></Suspense>
      ) : null}

    </div>
  );
}
