import type { QuizKind } from "./types/quiz";

/**
 * 새 창으로 여는 화면들의 주소.
 *
 * 캘린더도 강의 화면도 이 링크들을 쓰므로 어느 한쪽에 두면 반대쪽이 그 조각을
 * 통째로 끌고 온다. 주소만 여기 모은다.
 */

/** 강의 상세는 새 창이다. 캘린더를 잃지 않고 자료를 여닫으라는 뜻이다. */
export function lectureHref(lecture: { subject: string; runId: string }) {
  return `/lectures/${encodeURIComponent(lecture.subject)}/${encodeURIComponent(lecture.runId)}`;
}

/**
 * 웹 풀이도 전용 창이다. **예습·복습 둘 다.**
 *
 * 강의 화면 안에서 풀던 것을 밖으로 냈다. 푸는 동안 화면에 있어야 하는 것은
 * 문항과 답과 슬라이드뿐인데, 강의 화면에는 그 위아래로 필기·덱·링크가 서 있다.
 * 캘린더에서 곧장 열 수 있게 되는 것은 덤이다 — 전에는 강의 화면을 거쳐야 했다.
 *
 * 주소의 낱말이 서버 경로와 같다(`prequiz` / `mainquiz`). 둘을 따로 적으면
 * 언젠가 한쪽만 바뀐다.
 */
export function quizPath(kind: QuizKind) {
  return kind === "pre" ? "prequiz" : "mainquiz";
}

export function quizHref(kind: QuizKind, lecture: { subject: string; runId: string }) {
  return `/${quizPath(kind)}/${encodeURIComponent(lecture.subject)}/${encodeURIComponent(lecture.runId)}`;
}

/**
 * 창 이름. 같은 강의의 같은 갈래를 다시 누르면 새 창이 아니라 열려 있던 창이
 * 다시 뜬다 — 캘린더와 강의 화면 양쪽에 버튼이 있어서 누르는 자리가 둘이다.
 * **갈래가 이름에 들어가야 예습 창과 복습 창이 서로를 밀어내지 않는다.**
 *
 * **`rel="noreferrer"`를 같이 주면 안 된다.** `noopener`가 딸려 오고, 명세상
 * `noopener`는 창 이름을 무시하고 늘 새 창을 연다. 같은 출처의 우리 화면이라
 * `opener`가 이어져 있어도 잃는 것이 없다.
 */
export function quizWindow(kind: QuizKind, lecture: { subject: string; runId: string }) {
  return `${quizPath(kind)}:${lecture.subject}/${lecture.runId}`;
}

/**
 * Quiz Bank 풀이 창(2026-10-04). 웹 풀이와 같은 까닭으로 전용 창이다 — 문항·답·슬라이드만 있으면 된다.
 * 다음 문항은 서버가 고른다(`server/app/study_engine/`).
 */
export function bankHref(lecture: { subject: string; runId: string }) {
  return quizHref("main", lecture);
}

export function bankWindow(lecture: { subject: string; runId: string }) {
  return quizWindow("main", lecture);
}

export function legacyMainHref(lecture: { subject: string; runId: string }) {
  return `/legacy-mainquiz/${encodeURIComponent(lecture.subject)}/${encodeURIComponent(lecture.runId)}`;
}
