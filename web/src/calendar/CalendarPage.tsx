import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "../api";
import { usePreviewLink } from "../bridge/previewBridge";
import type { TimetableEvent } from "../types";
import { CalendarGrid } from "./CalendarGrid";
import { EventChip } from "./EventChip";
import { EventPanel } from "./EventPanel";
import {
  addDays,
  formatWeekTitle,
  startOfWeek,
  toCalendarEntries,
  type CalendarEntry,
  type CalendarMode,
} from "./entries";

/**
 * 캘린더가 홈이다.
 *
 * 시간표만으로 완성된 화면이고, 파이프라인 산출물은 나중에 점으로 붙는다.
 * 그래서 첫 배포에 강의 자료가 하나도 없어도 쓸모가 있다.
 */
export function CalendarPage() {
  const [events, setEvents] = useState<TimetableEvent[] | null>(null);
  const [error, setError] = useState("");
  const [mode, setMode] = useState<CalendarMode>("week");
  const [anchorDate, setAnchorDate] = useState(() => new Date());
  const [opened, setOpened] = useState<CalendarEntry | null>(null);

  /**
   * 확장이 만들어 준 예습 링크를 받아 저장한다.
   *
   * **관리자만 성공한다.** `PUT …/preview`가 러너·관리자 게이트 뒤에 있고, 그것이
   * 곧 "관리자가 만든 대화라야 Pre-Quiz의 재료가 된다"는 규칙이다. 일반 사용자는
   * 403을 받고 조용히 지나간다 — 예습 대화 자체는 이미 열렸으므로 그 사람에게는
   * 아무것도 실패하지 않았다.
   */
  usePreviewLink(
    useCallback(async ({ lectureId, kind, url }) => {
      const [subject, runId] = lectureId.split("/");
      if (!subject || !runId) return;
      const field = kind === "chatgpt_share" ? "shareUrl" : "conversationUrl";
      await api(`/api/admin/lectures/${encodeURIComponent(subject)}/${encodeURIComponent(runId)}/preview`, {
        method: "PUT",
        body: JSON.stringify({ provider: "chatgpt", [field]: url }),
      });
      // 저장된 링크가 패널에 바로 보이도록 다시 불러 온다.
      const payload = await api<{ events: TimetableEvent[] }>("/api/timetable");
      setEvents(payload.events);
    }, []),
  );

  useEffect(() => {
    api<{ events: TimetableEvent[] }>("/api/timetable")
      .then((payload) => setEvents(payload.events))
      .catch((cause: Error) => setError(cause.message));
  }, []);

  const entries = useMemo(() => toCalendarEntries(events ?? []), [events]);

  const heading =
    mode === "week"
      ? formatWeekTitle(startOfWeek(anchorDate))
      : `${anchorDate.getFullYear()}년 ${anchorDate.getMonth() + 1}월`;

  function step(direction: -1 | 1) {
    setAnchorDate((current) =>
      mode === "week"
        ? addDays(current, 7 * direction)
        : new Date(current.getFullYear(), current.getMonth() + direction, 1),
    );
  }

  if (error) return <p className="notice is-error">{error}</p>;
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
            />
          )}
        />

        {/* 색이 두 가지를 뜻하게 됐으니 둘 다 적는다 — 색상은 범주, 진하기는
            학습 상태. 규칙이 어디에도 안 적혀 있으면 아무도 못 읽는다. */}
        <div className="calendar-legend">
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
          <span className="legend-group">
            <span>
              <i className="legend-ramp" aria-hidden="true">
                <i />
                <i />
                <i />
              </i>
              띠가 진할수록 할 일이 있습니다
            </span>
          </span>
          <span className="legend-group">
            <span>
              <i className="chip-dot is-notes" /> 필기
            </span>
            <span>
              <i className="chip-dot is-quiz" /> 퀴즈
            </span>
            <span>
              <i className="chip-dot is-preview" /> 예습
            </span>
          </span>
          <small className="legend-note">어느 칸이든 누르면 자세히 볼 수 있습니다.</small>
        </div>
      </div>

      {/* key로 칸이 바뀔 때 패널 안의 상태(고른 강의·불러온 자료)를 갈아 끼운다. */}
      {opened ? <EventPanel key={opened.id} entry={opened} onClose={() => setOpened(null)} /> : null}
    </div>
  );
}
