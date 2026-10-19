import { api } from "./api";
import type { Me } from "./types/account";
import type { TimetableEvent } from "./types/lectures";

/**
 * 홈에서만 계정과 가벼운 시간표를 같이 띄운다. 다른 화면은 계정만 읽는다.
 *
 * 껍데기(`App`)가 `me`를 받기 전에는 "불러오는 중"에서 멈추므로 `CalendarPage`가
 * 마운트조차 못 한다. 그래서 아무것도 안 하면 두 요청이 **직렬로 선다** —
 * `/api/timetable`은 `/api/me`의 결과를 한 글자도 안 쓰는데 뒤에서 기다린다.
 * 왕복이 한 번 통째로 늘어난다.
 *
 * 세션이 잡히는 순간 둘을 같이 띄워 두면 캘린더가 마운트될 때 시간표는 이미
 * 와 있거나 오는 중이다.
 *
 * 승인 전 사용자에게는 `/api/timetable`이 403으로 떨어지는데, 그 갈래는
 * `me.isApproved`가 먼저 막아서 화면에 닿지 않는다 — 버려지는 요청 하나다.
 */
type Timetable = { events: TimetableEvent[] };

let mePending: Promise<Me> | null = null;
let meValue: Me | null = null;
let timetablePending: Promise<Timetable> | null = null;
let timetableInFlight: Promise<Timetable> | null = null;
let timetableStarted = false;

/** 시간표의 제목·시간만 읽는다. 학습 집계는 화면에서 요청할 때 별도로 읽는다. */
export function loadTimetable(): Promise<Timetable> {
  if (!timetableInFlight) {
    const pending = api<Timetable>("/api/timetable?include_study=false");
    timetableInFlight = pending;
    const clear = () => { if (timetableInFlight === pending) timetableInFlight = null; };
    pending.then(clear, clear);
  }
  return timetableInFlight;
}

export function startFirstScreen(prefetchTimetable = false): void {
  if (!mePending) {
    mePending = api<Me>("/api/me").then((value) => {
      meValue = value;
      return value;
    });
    // 받을 곳이 아직 안 붙었는데 실패하면 unhandled rejection으로 뜬다. 여기서
    // 한 번 받아 두어도 원래 promise는 거절된 채 남아 호출부가 다시 받는다.
    mePending.catch(() => {});
  }
  if (prefetchTimetable && !timetableStarted) {
    timetableStarted = true;
    timetablePending = loadTimetable();
    timetablePending.catch(() => {});
  }
}

/** 지금 로그인한 사람. 값이 바뀌지 않으므로 한 번만 받아 둔다. */
export function getMe(): Promise<Me> {
  startFirstScreen();
  return mePending!;
}

/** 이미 와 있으면 그 값. 첫 렌더에서 요청 없이 쓰려고 쓴다. */
export function peekMe(): Me | null {
  return meValue;
}

/**
 * 미리 띄워 둔 시간표를 **한 번만** 넘긴다.
 *
 * `me`와 달리 시간표는 변한다 — 예습 링크가 붙거나 덱이 올라오면 점이 바뀐다.
 * 그래서 캐시로 두지 않고 넘긴 뒤 비운다. 관리 화면에 갔다 돌아와 캘린더가
 * 다시 마운트되면 그때는 새로 부른다(이 파일이 생기기 전과 같은 동작이다).
 */
export function takeTimetable(): Promise<Timetable> {
  const pending = timetablePending;
  if (pending) {
    // StrictMode의 같은 커밋 안 재마운트도 이미 완료된 선조회 응답을 공유한다.
    const clear = () => { if (timetablePending === pending) timetablePending = null; };
    pending.then(clear, clear);
  }
  return pending ?? loadTimetable();
}

/** 퀴즈에서 바로 시작한 경우에도 학습 전 미리 받은 시간표를 다시 쓰지 않는다. */
export function invalidateTimetable(): void {
  timetablePending = null;
  timetableInFlight = null;
}

/**
 * 로그아웃하면 버린다.
 *
 * 같은 탭에서 다른 사람이 로그인할 수 있다. 모듈에 남겨 두면 앞사람의 `me`와
 * 시간표가 그대로 보인다.
 */
export function resetFirstScreen(): void {
  mePending = null;
  meValue = null;
  timetablePending = null;
  timetableInFlight = null;
  timetableStarted = false;
}
