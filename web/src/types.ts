/** 로그인 직후 무엇을 그릴지 정하는 값. 승인 게이트를 지나지 않는 응답이다. */
export type Me = {
  id: string;
  email: string;
  isAdmin: boolean;
  isApproved: boolean;
};

export type AppUser = {
  id: string;
  email: string;
  isAdmin: boolean;
  isApproved: boolean;
  createdAt: string | null;
};

export type EventCategory = "lecture" | "practice" | "exam" | "holiday" | "elective" | "study";

/**
 * 강의 칩에 찍히는 점. 있다/없다만 안다.
 *
 * `quiz`는 본덱(`main_apkg`)만이다. 예습덱은 `prequiz`가 따로 든다 — 둘은
 * 쓰는 시점이 달라서 같은 점으로 그리면 어느 쪽도 안 뜻한다.
 */
export type Marks = {
  notes: boolean;
  quiz: boolean;
  prequiz: boolean;
  preview: boolean;
};

/**
 * 웹 예습퀴즈를 몇 개까지 풀었는가.
 *
 * **이 사람의 값이다.** 그리고 잴 수 있는 유일한 "했다"이기도 하다 — 덱은
 * apkg로 나가 Anki에서 풀리므로 서버에 기록이 없다.
 */
export type PrequizProgress = {
  total: number;
  answered: number;
};

export type LectureRef = {
  subject: string;
  runId: string;
  title: string;
  professors: string[];
  marks: Marks;
  /** 웹에서 풀 문항이 없으면 없다. "안 풀었다"와 "잴 것이 없다"는 다르다. */
  prequizProgress: PrequizProgress | null;
};

export type TimetableEvent = {
  id: string;
  date: string;
  startTime: string;
  endTime: string;
  title: string;
  details: string;
  professor: string;
  category: EventCategory;
  course: string;
  slot: number | null;
  /** 한 칸에 여러 강의가 붙을 수 있다. 선택형 과목이 그렇다. */
  lectures: LectureRef[];
};

export type LectureFile = {
  id: string;
  kind: "notes_prev" | "notes_current" | "pre_apkg" | "main_apkg";
  label: string;
  filename: string;
  sizeBytes: number;
};

export type MissedItem = {
  itemId: string;
  stem: string;
  focus: string;
  retrievalTarget: string;
  explanation: string;
  slideNo: number | null;
  examHit: boolean;
};

export type LectureDetail = {
  subject: string;
  runId: string;
  uid: string;
  date: string;
  slot: number;
  slotEnd: number;
  startTime: string;
  title: string;
  professors: string[];
  author: string;
  version: number | null;
  course: string;
  files: LectureFile[];
  /**
   * `conversationUrl`은 관리자 응답에만 있다. 만든 계정에서만 열리는 값이라
   * 서버가 일반 사용자 응답에서 아예 빼고 내려보낸다.
   */
  preview: { provider: string; shareUrl: string; conversationUrl?: string } | null;
  /** 내 개인 예습 대화(`/c/`). 만든 계정에서만 열리므로 남의 것은 안 내려온다. */
  myPreview: { conversationUrl: string } | null;
  prequiz: { itemCount: number; answered: number; correct: number; missed: MissedItem[] } | null;
  runMeta?: Record<string, { reviewFlagged: number; slidesUnused: number; itemCount: number; builtAt: string | null }>;
};

export type QuizItem = {
  itemId: string;
  qtype: "mcq" | "short" | "ox";
  /** 마크다운 `**강조**`가 들어 있다. 부정형 발문을 놓치지 말라고 넣은 것이다. */
  stem: string;
  choices: string[] | null;
  attempt: { answered: string; correct: boolean } | null;
};

export type QuizPayload = {
  subject: string;
  runId: string;
  title: string;
  items: QuizItem[];
  answered: number;
  correct: number;
};

export type GradeResult = {
  itemId: string;
  correct: boolean;
  answer: string;
  explanation: string;
  sourceAnchor: string;
  slideNo: number | null;
  slideUrl: string | null;
};

export type AdminRow = {
  subject: string;
  runId: string;
  date: string;
  slot: number;
  title: string;
  professors: string[];
  author: string;
  version: number | null;
  match: {
    timetableEventId: string | null;
    confirmed: boolean;
    eventTitle: string | null;
    eventDetails: string | null;
  };
  has: Record<string, boolean>;
  preItemCount: number;
  preview: { shareUrl: string; conversationUrl: string; provider: string } | null;
  runMeta: Record<string, { reviewFlagged: number; slidesUnused: number; itemCount: number; builtAt: string | null }>;
};

export type AdminOverview = {
  lectures: AdminRow[];
  courseAliases: { courseKey: string; course: string; subject: string }[];
  /** 과목으로 볼 만큼 자주 열리는 것만. 한 번짜리 특강·행사는 빠져 있다. */
  timetableCourses: { courseKey: string; course: string; sessions: number }[];
  subjects: string[];
};
