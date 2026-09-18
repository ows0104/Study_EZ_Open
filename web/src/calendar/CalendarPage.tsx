import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "../api";
import { BundleButton } from "../bundle/BundleButton";
import { decksIn, useBundleDecks } from "../bundle/decks";
import { bumpPreviewVersion, usePreviewLink } from "../bridge/previewBridge";
import { takeTimetable } from "../firstScreen";
import { previewProviders, type PreviewProvider, type TimetableEvent } from "../types";
import { useMe } from "../useMe";
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
  // 자리 둘이 무엇을 세는지가 이것으로 갈린다. 칸마다 묻지 않고 여기서 한 번
  // 묻는다 — `useMe`는 훅이라 칸 안에서 부르면 강의 수만큼 붙는다.
  const isAdmin = Boolean(useMe()?.isAdmin);
  /**
   * 덱이 어디 있고 무엇을 받아 갔나. **여기 한 곳에서만 부른다** — 날짜 머리
   * 다섯과 열려 있는 패널이 같은 값을 봐야 하고, 칸마다 훅을 걸면 강의 수만큼
   * 요청이 붙는다(`isAdmin` 을 여기서 한 번 묻는 것과 같은 이유다).
   */
  const bundles = useBundleDecks();

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
  usePreviewLink(
    useCallback(async ({ lectureId, kind, url }) => {
      const [subject, runId] = lectureId.split("/");
      if (!subject || !runId) return;
      const path = `${encodeURIComponent(subject)}/${encodeURIComponent(runId)}`;
      const shared = kind.endsWith("_share");
      const provider = (shared ? kind.slice(0, -6) : kind) as PreviewProvider;
      if (!previewProviders.includes(provider)) return;
      if (shared) {
        await api(`/api/admin/lectures/${path}/preview`, {
          method: "PUT",
          body: JSON.stringify({ provider, shareUrl: url }),
        });
      } else {
        await api(`/api/lectures/${path}/my-preview`, {
          method: "PUT",
          body: JSON.stringify({ provider, conversationUrl: url }),
        });
      }
      // 칸의 점(marks)과 열려 있는 패널을 둘 다 갱신한다. 시간표만 다시 부르면
      // 패널은 자기가 부른 강의 상세를 그대로 들고 있어서 안 바뀐다.
      bumpPreviewVersion();
      const payload = await api<{ events: TimetableEvent[] }>("/api/timetable");
      setEvents(payload.events);
    }, []),
  );

  useEffect(() => {
    takeTimetable()
      .then((payload) => setEvents(payload.events))
      .catch((cause: Error) => setError(cause.message));
  }, []);

  /**
   * 강의 상세 조각을 미리 받아 둔다.
   *
   * 강의 상세는 **새 창**에서 열린다. 그 창은 문서가 따로라 이 창의 메모리를
   * 물려받지 않지만 HTTP 캐시는 같이 쓴다. 여기서 한 번 받아 두면 새 창은
   * 디스크에서 꺼내 쓴다 — 쪼갠 대가인 왕복 한 번이 칸을 누르기 전에 끝나 있다.
   */
  useEffect(() => {
    void import("../lecture/LecturePage");
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
              isAdmin={isAdmin}
            />
          )}
          /* 격자 맨 아랫줄의 하루치 모아받기. 예습과 복습을 갈라 둔다 — 쓰는
             때가 다르고(강의 전 · 강의 후) 덱 나무도 이미 갈라져 있다. 덱이
             없는 날에는 `BundleButton` 이 스스로 아무것도 안 그린다. */
          renderDay={(dateKey) => {
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
          }}
        />

        {/* 왼쪽 띠는 범주만 뜻한다. 학습 상태는 점이 말한다 — 띠까지 상태로
            흔들면 같은 것을 두 번 말하는 것이고, 점 쪽이 훨씬 정확하다. */}
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
          {/* 자리 둘을 예습·복습 두 줄로 늘어놓지 않는다. 세 단계는 두 자리가
              똑같이 쓰므로 한 번만 적고, 어느 쪽이 예습이고 복습인지는 딱지의
              모양이 말한다 — 칸에서도 모양이 그 일을 한다. */}
          <span className="legend-group is-phase">
            <b>
              <span>
                예습 <i className="legend-shape is-pre" />
              </span>
              <span>
                복습 <i className="legend-shape is-main" />
              </span>
            </b>
            {/* 관리자는 같은 모양으로 다른 것을 읽는다 — 자기가 어디까지 올려
                놨는가다. 범례도 같이 갈지 않으면 채운 도형이 「내가 했음」으로
                읽혀서, 아무것도 안 푼 강의가 다 한 것으로 보인다. */}
            {isAdmin ? (
              <>
                <span>
                  <i className="chip-slot is-pre is-none" /> 링크·필기 없음
                </span>
                <span>
                  <i className="chip-slot is-pre is-ready" /> 덱 없음
                </span>
                <span>
                  <i className="chip-slot is-pre is-done" /> 덱 있음
                </span>
                <span>빈칸 — 작년 필기 없음</span>
              </>
            ) : (
              <>
                <span>
                  <i className="chip-slot is-user is-pre is-none" /> 아직
                </span>
                <span>
                  <i className="chip-slot is-user is-pre is-ready" /> 올라옴
                </span>
                <span>
                  <i className="chip-slot is-user is-pre is-done" /> 함
                </span>
              </>
            )}
          </span>
        </div>
      </div>

      {/* key로 칸이 바뀔 때 패널 안의 상태(고른 강의·불러온 자료)를 갈아 끼운다. */}
      {opened ? (
        <EventPanel
          key={opened.id}
          entry={opened}
          onClose={() => setOpened(null)}
          bundleDecks={bundles.decks}
          onBundleDone={bundles.reload}
        />
      ) : null}
    </div>
  );
}
