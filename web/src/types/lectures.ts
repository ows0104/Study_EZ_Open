import type { QuizProgress } from "./quiz";
import type { LectureMastery } from "./mastery";
import type { CardReviewCount } from "./admin";
import type { BankSummary, BankSource } from "./bank";

/** 예습 대화를 열 수 있는 AI 서비스. 확장과 서버가 같은 세 값을 쓴다. */
export type PreviewProvider = "chatgpt" | "gemini" | "claude";

export const previewProviders: PreviewProvider[] = ["chatgpt", "gemini", "claude"];

export const previewProviderLabels: Record<PreviewProvider, string> = {
  chatgpt: "ChatGPT",
  gemini: "Gemini",
  claude: "Claude",
};

export type EventCategory = "lecture" | "practice" | "exam" | "holiday" | "elective" | "study";

/**
 * 강의에 무엇이 올라와 있는가. 있다/없다만 안다.
 *
 * **다섯 칸이 관리자 체크리스트와 하나씩 짝이다.** 앞 셋이 예습 자리로, 뒤 둘이
 * 복습 자리로 묶여 칸의 점 둘이 된다.
 *
 * `quiz`는 학습 가능한 Main Quiz(Quizbank)다. 예습덱은 `prequiz`가 따로 든다 — 둘은
 * 쓰는 시점이 달라서 같은 점으로 그리면 어느 쪽도 안 뜻한다.
 */
export type Marks = {
  /** 작년 필기. 예습으로 읽는 것이라 올해 것과 다른 자리에 선다. */
  notesPrev: boolean;
  preview: boolean;
  prequiz: boolean;
  notesCurrent: boolean;
  quiz: boolean;
};

/**
 * 이 사람이 받아 갔는가. 자리 둘로 묶여 온다.
 *
 * **덱에서 "했다"를 아는 유일한 길이다.** apkg는 Anki에서 풀리므로 풀이 기록이
 * 서버에 없지만, 파일이 나가려면 서명을 받아 가야 하고 그 서명은 사용자가
 * 버튼을 눌러야 나간다. 그래서 이것은 *받아 갔다*지 *풀었다*가 아니다.
 */
export type Grabbed = {
  pre: boolean;
  main: boolean;
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
  mastery?: LectureMastery | null;
  subject: string;
  runId: string;
  title: string;
  professors: string[];
  marks: Marks;
  /** 웹에서 풀 문항이 없으면 없다. "안 풀었다"와 "잴 것이 없다"는 다르다. */
  prequizProgress: PrequizProgress | null;
  grabbed: Grabbed;
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
  kind: "notes_prev" | "notes_current" | "jokbo" | "pre_apkg" | "main_apkg";
  label: string;
  filename: string;
  sizeBytes: number;
  contentType?: string;
};

export type LectureDetail = {
  mastery?: LectureMastery | null;
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
  preview: { provider: PreviewProvider; shareUrl: string; conversationUrl?: string } | null;
  /** 내 개인 예습 대화. 만든 AI 계정에서만 열리므로 남의 것은 안 내려온다. */
  myPreview: { provider: PreviewProvider; conversationUrl: string } | null;
  prequiz: QuizProgress | null;
  /**
   * 복습 웹 풀이. **2026-08-31에 생겼고 그 전에 구운 편에는 없다.**
   * `null`이면 화면이 그 자리를 아예 안 그린다 — 덱만 있는 편과 같다.
   */
  mainquiz: QuizProgress | null;
  runMeta?: Record<string, RunMetaBrief>;
  /** 관리자에게만. 갈래마다 카드 수 · 걸린 것 · 그중 안 본 것 · 판정 건수.
   *  사이드 패널의 「카드 고치기」가 적는다. 웹 문항이 없는 갈래는 빠져 있다. */
  cardReview?: Partial<Record<"pre" | "main", CardReviewCount>>;
  /** Quiz Bank 요약(2026-10-04). 학생에게는 관리자가 연 은행만 온다 — 아니면 `null`. */
  bank: BankSummary | null;
  /** 관리자에게만. ChatGPT 에 붙일 자료와 그 ID(S1 올해 필기 · S2 족보 조각). */
  bankSources?: BankSource[];
  /** 관리자에게만. 프롬프트의 시험일 — 서버가 시간표에서 고른 날이다. */
  bankExamDate?: string;
};

/**
 * 구워진 덱 하나의 요약. `run.meta.json`에서 서버가 꺼내 둔 값이다.
 *
 * `sourceVersion`은 **무슨 판으로 구웠나**다. 지금 필기의 판(`AdminRow.version`)이
 * 그보다 크면 그 덱은 옛 자료로 만든 것이고, 한 편의 두 덱 중 하나만 다시 구운
 * 경우가 여기서 갈려 보인다. 파일명을 못 읽으면 `null`이다 — 1로 메우면 「같은
 * 판」으로 읽힌다.
 */
export type RunMetaBrief = {
  reviewFlagged: number;
  slidesUnused: number;
  itemCount: number;
  builtAt: string | null;
  sourceVersion: number | null;
};
