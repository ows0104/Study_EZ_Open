// ---------------------------------------------------------------- Quiz Bank (2026-10-04)
//
// ChatGPT 가 만든 문제은행을 서버 Study Engine 으로 푼다(`server/app/routes/bank.py`).
// 문항 필드 이름은 서버가 저장한 꼴 그대로(snake_case)다 — 은행 JSON 을 옮겨 적지 않고 싣는다.

export type BankTimeline = {
  /** 관리자에게만. 삭제 전 동시 변경 확인용 버전. */
  deleteVersion?: string | null;
  /** 문제은행 공유 주소는 관리자에게만 전달한다. */
  shareUrl?: string;
  /** 공유 링크를 새로 저장한 서버 시각. 기존 링크는 null. */
  linkedAt?: string | null;
  /** 최종퀴즈 결과 업로드를 서버가 받아 저장한 시각. */
  builtAt: string | null;
};

export type BankSummary = BankTimeline & {
  coverage?: BankCoverage | null;
  shareUrl?: string;
  status: "linked" | "responded" | "building" | "ready" | "invalid" | "failed";
  open: boolean;
  buildId: string;
  questionCount: number;
  /** Optional을 제외한 분모와 현재 은행에서 본 고유 문항 수. */
  studyQuestionCount: number;
  seenQuestionCount: number;
  conceptCount: number;
  builtAt: string | null;
  /** 검증을 통과해 공부할 수 있는가. */
  usable: boolean;
  publicationWarning?: string;
  /** 아래는 관리자에게만. */
  respondedAt?: string | null;
  promptVersion?: string;
  conversationUrl?: string;
  revision?: Record<string, unknown> | null;
  message?: string;
  reviewCounts?: { ok: number; doubt: number; wrong: number } | null;
  errorCount?: number;
  /** 검증에 걸려 빼고 연 문항(2026-10-05 — 「걸린 문항만 빼고 연다」). */
  dropped?: { questionId: string; errors: string[] }[];
};

export type BankCoverage = {
  classification?: { status: "verified"; classifiedCount: number; recallFirstCount: number; comparisonCount: number; checkedAt: string } | null;
  pointCount?: number | null;
  coveredPointCount?: number | null;
  status: "verified" | "partial" | "stale";
  totalPages: number;
  checkedPages: number;
  excludedPages: number;
  unreadablePages: number;
  gapCount: number;
  addedQuestions: number;
  addedMcq: number;
  checkedAt: string;
  sourceFilename: string;
  issues?: { page: number; note: string; facts: string[] }[];
};

export type BankSource = {
  id: string;
  kind: "notes_current" | "jokbo";
  assetId: string;
  filename: string;
  contentType: string;
};

export type BankFormat = "basic" | "cloze" | "list" | "ox" | "mcq" | "multi_select" | "matching" | "sequence";

export type BankRating = "Again" | "Hard" | "Good" | "Easy";
export type BankTier = "Essential" | "Core" | "Important" | "Optional";

/** 답이 빠진 문항. 답·채점 단위는 `reveal` 로만 온다. */
export type BankQuestion = {
  stimuli?: {sha256:string; width:number; height:number; url:string; alt:string}[];
  personalAdded?: boolean;
  presentationSeed?: string;
  /** The API has placed the ordered matching column on the left. */
  matchingOrdered?: boolean;
  mcq_mode?: "recall_first" | "comparison" | "none";
  personalEdited?: boolean;
  question_id: string;
  personalTier?: boolean;
  originalTier?: BankTier;
  targetMastery?: number;
  concept_id: string;
  tier: BankTier;
  advanced?: boolean;
  importance: number;
  format: BankFormat;
  retrieval_direction: string;
  question: string;
  source_refs: { source_id: string; locator: string }[];
  conflict_id: string;
  options: { id: string; text: string }[];
  matching_left: string[];
  matching_right: string[];
  sequence_items: string[];
};

export type BankReview = {
  question_id: string;
  verdict: "ok" | "doubt" | "wrong";
  note: string;
  suggested_answer: string;
};

export type BankAnswer = {
  personalEdited?: boolean;
  personalAnswer?: boolean;
  answer: string;
  explanation?: string;
  answerUnits: string[];
  correctOptionIds: string[];
  answerPairs: { left: string; right: string }[];
  correctOrder: string[];
  /** 문항이 인용한 필기 쪽들. 한 문항이 여러 장일 수 있다. */
  slides: BankSlide[];
  /** 실제로 인용한 족보 문항의 원본 PDF 지면. */
  jokboSlides?: { page: number; url: string; pdfFilename: string; references: string[]; primary?: boolean; embedded?: boolean;
    questions?: { reference: string; stem: string; options: string[]; needsFigure?: boolean;
      answer?: string | null; objection?: string | null;
      answerReview?: {
        answer: string; answerText: string;
        status: "verified" | "corrected" | "doubt" | "unresolved";
        confidence: "high" | "medium" | "low"; reason: string;
        sources: { kind: "lecture" | "exam" | "external"; locator: string; url: string; support: string }[];
      } }[] }[];
  evidenceStatus?: {
    category: "exam_only" | "partial_support" | "source_conflict" | "unsupported" | "uncertain";
    reason: string; missingClaim?: string; primaryAvailable?: boolean;
  } | null;
  /** 외부지식 검토. 막지 않고 표시만 한다. */
  medicalReview: BankReview | null;
  reviewIssues?: string[];
  /** 충돌 문항이면 각 출처의 말과 고른 근거(프롬프트 v1.2). 옛 API 에는 없다. */
  conflict?: string;
  /** 자료 밖 내용을 외부 의학지식으로 썼다(출처 `EXT`). */
  external?: boolean;
};

export type BankSlide = {
  page: number; url: string; primary?: boolean;
  sourceId?: string; sourceRunId?: string; sourceFilename?: string;
};

export type BankCatalogItem = { question: BankQuestion; pages: number[]; suspended: boolean;
  excludedStatus?: 'excluded' | 'restored' | 'deleted' | null; excludedReason?: string };
export type BankCatalog = {
  buildId: string; title: string; subject: string; runId: string;
  questions: BankCatalogItem[]; slides: BankSlide[];
};
export type BankCatalogAnswer = { question: BankQuestion; answer: BankAnswer };

/** 관리자가 보는 문항 — 은행 JSON 그대로라 답 칸도 snake_case 다. */
export type BankOptionPool = {
  pool_id: string; select_count: number; correct_when: "true" | "false";
  candidates: { candidate_id: string; true_text: string; false_text: string;
    true_explanation: string; false_explanation: string;
    source_refs: { source_id: string; locator: string }[] }[];
};
export type BankFullQuestion = BankQuestion & {
  explanation?: string;
  option_pools?: BankOptionPool[];
  item_difficulty: number;
  prerequisites: string[];
  exam_rationale: string;
  answer: string;
  answer_units: string[];
  correct_option_ids: string[];
  answer_pairs: { left: string; right: string }[];
  correct_order: string[];
};

export type BankCardDecision = {
  action: "edit" | "accept" | "delete";
  original: BankFullQuestion;
  question: BankFullQuestion;
  by: string;
  at: string;
};
export type BankReviewCard = {
  question: BankFullQuestion;
  errors: string[];
  medicalReview: BankReview | null;
  edit: BankCardDecision | null;
};
export type BankReviewGroup = {
  subject: string; runId: string; title: string; date: string; buildId: string;
  cards: BankReviewCard[];
  concepts: { id: string; title: string }[];
  sources?: BankSource[];
  conflicts?: { id: string; description: string }[];
  questions: { id: string; question: string; available: boolean }[];
};
export type BankReviewBoard = { banks: BankReviewGroup[]; open: number; done: number };

export type BankReportStatus = "open" | "resolved" | "wontfix";

/** 학생 신고 한 건(`GET /api/admin/bank-feedback`). */
export type BankReport = {
  highlighted?: boolean;
  id: number;
  category: string;
  comment: string;
  status: BankReportStatus;
  email: string;
  createdAt: string | null;
  /** 지금 은행보다 옛 빌드에서 온 신고. 같은 ID 에 다른 문항이 앉았을 수 있다. */
  stale: boolean;
};

/** 같은 문항에 모인 신고들. `question` 은 **지금 은행의 것**이고, 지금 은행에 없으면 `null`. */
export type BankReportGroup = {
  subject: string;
  runId: string;
  questionId: string;
  title: string;
  date: string;
  question: BankFullQuestion | null;
  medicalReview: BankReview | null;
  reports: BankReport[];
};

export type BankReportBoard = { questions: BankReportGroup[]; open: number; done: number };

export type BankDimension = {
  concept_id: string;
  title: string;
  direction: string;
  before: number;
  after: number;
  target: number;
};

export type BankSession = {
  session_id: string;
  status: "active" | "complete";
  reason: string | null;
  size: number | null;
  reviewed: number;
  ratings: Record<BankRating, number>;
  core_before: number;
  core_after: number;
  improved: BankDimension[];
  weaknesses: BankDimension[];
  started_at: number;
  ended_at: number | null;
};

export type BankRead = {
  personalQuestions?: { questionId: string; question: string; tier: BankTier }[];
  suspendedQuestions?: { questionId: string; question: string }[];
  undoToken?: string | null;
  lectureGoal?: import("./studyPlan").LectureGoal | null;
  mastery?: import("./mastery").LectureMastery | null;
  summary: BankSummary;
  examDate: string;
  sizes: number[];
  defaultSize: number;
  session: BankSession | null;
  previousSessions: BankSession[];
  /**
   * 개념 지도. 첫 회차 전에도 온다(숙련도가 다 0). 계산은 서버 엔진(`concept_map`)이 한다.
   * **없을 수 있다** — 푸시는 화면만 내고 API 는 손으로 올려서, 이 칸이 없는 API 가 뜬 채일 때가 있다.
   */
  conceptMap?: BankConcept[];
};

/** 개념 하나와 이 사람의 방향별 숙련도. 방향은 문항이 있는 것만 온다. */
export type BankConcept = {
  concept_id: string;
  title: string;
  /** 그래프용 요약. 옛 은행·API에는 없으므로 전체 제목으로 대체한다. */
  graph_title?: string;
  core_facts: string[];
  importance: number;
  importance_rationale: string;
  concept_difficulty: number;
  tier: BankTier;
  exam_signal_strength: string;
  related_concepts: string[];
  directions: { direction: string; mastery: number; target: number; reviews: number; questions: number }[];
  /** 방향마다 목표 대비 비율(1에서 자름)의 평균. 그래프의 색이다. */
  progress: number;
};

export type BankNext = {
  choicesShown?: boolean;
  lecture?: { subject: string; runId: string; title?: string } | null;
  batchGoal?: import("./studyPlan").LectureGoal | null;
  undoLecture?: { subject: string; runId: string } | null;
  undoToken?: string | null;
  waiting?: boolean;
  lectureGoal?: import("./studyPlan").LectureGoal | null;
  question: BankQuestion | null;
  /** Warm the current question's images without recording a reveal. Older APIs omit this. */
  preloadSlides?: BankSlide[];
  reviewToken?: string;
  selectionTicket?: string;
  days?: number;
  examDate?: string;
  session?: BankSession | null;
  answer?: BankAnswer | null;
  /** 회차가 끝났거나 지금 낼 것이 없을 때. */
  summary?: BankSession | null;
  reason?: string;
  retryAt?: number;
};
