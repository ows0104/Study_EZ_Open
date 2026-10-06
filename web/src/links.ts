import type { QuizKind } from "./types/quiz";

/**
 * 같은 탭에서 이동하는 학습 화면들의 주소.
 *
 * 캘린더도 강의 화면도 이 링크들을 쓰므로 어느 한쪽에 두면 반대쪽이 그 조각을
 * 통째로 끌고 온다. 주소만 여기 모은다.
 */

/** 강의 상세 주소. */
export function lectureHref(lecture: { subject: string; runId: string }) {
  return `/lectures/${encodeURIComponent(lecture.subject)}/${encodeURIComponent(lecture.runId)}`;
}

/**
 * 웹 풀이도 같은 탭 안의 별도 화면이다. **예습·복습 둘 다.**
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
 * Quiz Bank 풀이 화면. 문항·답·슬라이드를 같은 탭에서 확인한다.
 * 다음 문항은 서버가 고른다(`server/app/study_engine/`).
 */
export function bankHref(lecture: { subject: string; runId: string }) {
  return quizHref("main", lecture);
}

export function legacyMainHref(lecture: { subject: string; runId: string }) {
  return `/legacy-mainquiz/${encodeURIComponent(lecture.subject)}/${encodeURIComponent(lecture.runId)}`;
}
