export type EventCategory = "lecture" | "practice" | "exam" | "holiday" | "elective" | "study";

/** 강의 칩에 찍히는 점. 있다/없다만 안다. */
export type Marks = {
  notes: boolean;
  quiz: boolean;
  prequiz: boolean;
  preview: boolean;
};

export type LectureRef = {
  subject: string;
  runId: string;
  title: string;
  professors: string[];
  marks: Marks;
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
