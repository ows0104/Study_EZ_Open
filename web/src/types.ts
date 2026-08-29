/** 로그인 직후 무엇을 그릴지 정하는 값. 승인 게이트를 지나지 않는 응답이다. */
export type Me = {
  id: string;
  email: string;
  isAdmin: boolean;
  isApproved: boolean;
};

/** 예습 대화를 열 수 있는 AI 서비스. 확장과 서버가 같은 세 값을 쓴다. */
export type PreviewProvider = "chatgpt" | "gemini" | "claude";

export const previewProviders: PreviewProvider[] = ["chatgpt", "gemini", "claude"];

export const previewProviderLabels: Record<PreviewProvider, string> = {
  chatgpt: "ChatGPT",
  gemini: "Gemini",
  claude: "Claude",
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
 * 강의에 무엇이 올라와 있는가. 있다/없다만 안다.
 *
 * **다섯 칸이 관리자 체크리스트와 하나씩 짝이다.** 앞 셋이 예습 자리로, 뒤 둘이
 * 복습 자리로 묶여 칸의 점 둘이 된다.
 *
 * `quiz`는 본덱(`main_apkg`)만이다. 예습덱은 `prequiz`가 따로 든다 — 둘은
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
  kind: "notes_prev" | "notes_current" | "pre_apkg" | "main_apkg";
  label: string;
  filename: string;
  sizeBytes: number;
};

export type MissedItem = {
  itemId: string;
  stem: string;
  answer: string;
  /** 왜 이것이 「꼭 반드시」인가 — spine·vocabulary·mechanism·clinical·repeated. */
  focus: string;
  cardType: string;
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
  preview: { provider: PreviewProvider; shareUrl: string; conversationUrl?: string } | null;
  /** 내 개인 예습 대화. 만든 AI 계정에서만 열리므로 남의 것은 안 내려온다. */
  myPreview: { provider: PreviewProvider; conversationUrl: string } | null;
  prequiz: { itemCount: number; answered: number; correct: number; missed: MissedItem[] } | null;
  runMeta?: Record<string, { reviewFlagged: number; slidesUnused: number; itemCount: number; builtAt: string | null }>;
};

/**
 * 예습 카드 한 장. **보기가 없다** — 자유회상이고 채점은 본인이 한다.
 *
 * `answer`도 `explanation`도 여기 없다. 답을 편 사람만 `reveal`로 받아 가고,
 * 그래야 「맞았다」가 무언가를 뜻한다.
 */
export type QuizItem = {
  itemId: string;
  /** 푸는 방식은 셋 다 같다. 화면이 꼴만 달리 그린다. */
  qtype: "basic" | "cloze" | "ox";
  stem: string;
  focus: string;
  cardType: string;
  examHit: boolean;
  attempt: { correct: boolean } | null;
};

export type QuizPayload = {
  subject: string;
  runId: string;
  title: string;
  items: QuizItem[];
  answered: number;
  correct: number;
};

/** `reveal`이 주는 것. 펴 보기만으로는 아무것도 기록되지 않는다. */
export type RevealResult = {
  itemId: string;
  answer: string;
  explanation: string;
  sourceAnchor: string;
  slideNo: number | null;
  slideUrl: string | null;
};

/** 관리자가 강의마다 채우는 다섯 칸. 서버의 `CHECKLIST_ITEMS`와 순서까지 같다. */
export const checklistItems = [
  "notes_prev",
  "preview",
  "pre_apkg",
  "notes_current",
  "main_apkg",
] as const;

export type ChecklistItem = (typeof checklistItems)[number];

/** `waived`는 "이 강의엔 해당 없음"으로 관리자가 닫은 칸이다. */
export type ChecklistState = "done" | "waived" | "todo";

/** 러너가 아직 안 집었거나(`queued`), 만드는 중이거나(`running`), 끝났거나. */
export type PrequizJobState = "queued" | "running" | "done" | "failed";

/** 무엇을 만드는 일감인가. 재료도 명령도 갈린다 — 예습은 예습 대화와 작년 필기로,
 *  복습은 올해 필기로 만든다. */
export type DeckKind = "pre" | "main";

/**
 * 「덱 만들기」를 누른 것. 만드는 곳은 노트북이라 여기서는 상태만 본다.
 *
 * `stage`는 러너가 하위 프로세스의 `── ` 줄을 그대로 올려 준 것이다. 한 편에
 * 15분이 걸려서, 「도는 중」만으로는 멈춘 것과 구별이 안 된다.
 */
export type PrequizJob = {
  id: number;
  subject: string;
  runId: string;
  kind: DeckKind;
  state: PrequizJobState;
  stage: string;
  message: string;
  requestedBy: string;
  /** 「다시 만들기」로 선 일감인가. 러너가 이미 만든 것을 버리고 처음부터 만든다. */
  force: boolean;
  createdAt: string;
  updatedAt: string;
};

/** 노트북이 마지막으로 살아 있다고 알린 시각. 없으면 한 번도 안 붙은 것이다. */
export type RunnerBeat = { lastSeen: string; busy: boolean; note: string };

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
  /** 이 편의 가장 최근 일감. **갈래를 안 가린다** — 관리 화면은 「러너가 안 붙었는데
   *  기다리는 일감이 있다」만 세므로, 그 수에는 예습도 복습도 같이 들어간다.
   *  끝난 것도 남는다 — 실패가 조용히 사라지면 안 된다. */
  prequizJob: PrequizJob | null;
  preview: { shareUrl: string; conversationUrl: string; provider: PreviewProvider } | null;
  runMeta: Record<string, { reviewFlagged: number; slidesUnused: number; itemCount: number; builtAt: string | null }>;
};

export type AdminOverview = {
  lectures: AdminRow[];
  courseAliases: { courseKey: string; course: string; subject: string }[];
  /** 과목으로 볼 만큼 자주 열리는 것만. 한 번짜리 특강·행사는 빠져 있다. */
  timetableCourses: { courseKey: string; course: string; sessions: number }[];
  subjects: string[];
  runner: RunnerBeat | null;
};
