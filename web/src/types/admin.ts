import type { PrequizJob, RunnerBeat } from "./jobs";
import type { PreviewProvider, RunMetaBrief } from "./lectures";
import type { BankSummary } from "./bank";

/** 관리자가 강의마다 채우는 다섯 칸. 서버의 `CHECKLIST_ITEMS`와 순서까지 같다. */
export const checklistItems = [
  "notes_prev",
  "preview",
  "pre_apkg",
  "notes_current",
  "bank",
] as const;

export type ChecklistItem = (typeof checklistItems)[number];

/** `waived`는 "이 강의엔 해당 없음"으로 관리자가 닫은 칸이다. */
export type ChecklistState = "done" | "waived" | "todo";

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
  /** 관리자가 채우는 다섯 칸. `done` | `waived` | `todo`. */
  checklist: Record<ChecklistItem, ChecklistState>;
  preItemCount: number;
  bank?: BankSummary | null;
  /** 이 편의 가장 최근 일감. **갈래를 안 가린다** — 관리 화면은 「러너가 안 붙었는데
   *  기다리는 일감이 있다」만 세므로, 그 수에는 예습도 복습도 같이 들어간다.
   *  끝난 것도 남는다 — 실패가 조용히 사라지면 안 된다. */
  prequizJob: PrequizJob | null;
  preview: { shareUrl: string; conversationUrl: string; provider: PreviewProvider } | null;
  runMeta: Record<string, RunMetaBrief>;
};

export type AdminOverview = {
  lectures: AdminRow[];
  courseAliases: { courseKey: string; course: string; subject: string }[];
  /** 과목으로 볼 만큼 자주 열리는 것만. 한 번짜리 특강·행사는 빠져 있다. */
  timetableCourses: { courseKey: string; course: string; sessions: number }[];
  subjects: string[];
  runner: RunnerBeat | null;
};

/** 사이트에서 카드 한 장에 내린 판정(`server/app/routes/cards.py`). */
export type CardAction = "ok" | "edit" | "delete";

/**
 * 관리자가 보는 카드 한 장 — **답까지 있다.**
 *
 * `flag` 는 걸린 까닭이다. `defect` 는 재현 검사가 문항 결함으로 가른 것이고
 * 2026-09-23 전까지 덱째로 배포를 막던 것, `axis` 는 빈칸이 무엇을 묻는지 안
 * 선 것이고 막은 적은 없다. 그날 전에 만든 편은 사유(`reason`)가 빈다.
 */
export type ReviewCard = {
  subject: string;
  runId: string;
  title: string;
  date: string;
  kind: "pre" | "main";
  itemId: string;
  ord: number;
  qtype: string;
  stem: string;
  /** 빈칸 카드의 원문(`{{c1::…}}`). 빈칸 카드는 이것을 고친다 — 답이 질문 안에 있다.
   *  2026-09-23 전에 올라온 카드는 비어 있고, 그때는 질문을 못 고친다. */
  sourceStem: string;
  answer: string;
  explanation: string;
  whyAsked?: string;
  learningSupport?: Record<string, string>;
  slideNo: number | null;
  slideUrl: string | null;
  flags: string[];
  /** 파이프라인이 올린 그대로. 고친 칸과 맞대 보려고 있다. */
  original: { stem: string; sourceStem: string; answer: string; explanation: string };
  flag: { why: "defect" | "axis"; reason: string; note: string; reproduced: string } | null;
  edit: { action: CardAction; editedBy: string; editedAt: string | null } | null;
};

export type CardReview = { cards: ReviewCard[]; open: number; done: number };

export type LectureCards = {
  subject: string;
  runId: string;
  title: string;
  kind: "pre" | "main";
  cards: ReviewCard[];
};

export type CardReviewCount = { cards: number; flagged: number; open: number; decided: number };
