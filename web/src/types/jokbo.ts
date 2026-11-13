/** 강의별 족보 풀이(jokbo-solve/1). 서버 `routes/jokbo.py`, 계약 `studyez_contracts/jokbo/solve.py`. */

export type JokboSectionKind = "same" | "other" | "unknown";
export type JokboAnswerStatus = "key" | "key-multiple" | "all-correct" | "missing";

export type JokboFigure = { file: string; w?: number; h?: number; url?: string };

export type JokboExplanation = {
  text: string;
  choiceNotes?: string[];
  caution?: string;
  basis: { kind: "notes" | "knowledge"; pages?: number[] };
  answerCheck: "agree" | "doubt" | "no-key";
  proposedAnswers?: number[];
};

export type JokboItem = {
  id: string;
  setId: string;
  year: number;
  yearLabel: string;
  number: number;
  sharedPrompt?: string;
  stem: string;
  choices: string[];
  answers: number[];
  answerMode: "one_of" | "all_of";
  selectCount: number;
  answerStatus: JokboAnswerStatus;
  allCorrect: boolean;
  answerNote?: string;
  verification: "verified" | "corrected" | "unverifiable" | "pending";
  correctionNote?: string;
  originalAnswers?: number[];
  repeatYears?: string[];
  figures?: JokboFigure[];
  explanation: JokboExplanation | null;
  /** 같은 문제가 나온 해 전부(합친 문제만). 대표 연도가 맨 앞. */
  years?: string[];
  /** 합친 다른 해 사본. answers는 이 문항의 선지 번호로 옮긴 것. */
  mergedFrom?: { id: string; yearLabel: string; number: number; answers: number[]; professors?: string[] }[];
  /** 해마다 답안지 답이 달랐다. */
  keyConflict?: boolean;
  /** 선지 한두 개만 다른 변형 묶음. 이어서 낸다. */
  variantGroup?: string;
};

export type JokboSection = {
  kind: JokboSectionKind;
  professors: string[];
  years: string[];
  itemIds: string[];
};

export type JokboDoc = {
  schema: "jokbo-solve/1";
  lecture: {
    eventId: string;
    runId: string | null;
    number: string;
    title: string;
    date: string;
    currentProfessors: string[];
    professorSource: "notes" | "timetable" | "none";
  };
  sections: JokboSection[];
  items: JokboItem[];
};

export type JokboSummary = {
  eventId: string;
  audience: "admin" | "all";
  items: number;
  sameItems: number;
  otherItems: number;
  unknownItems: number;
};

export type JokboResponse = JokboSummary & { uploadedAt?: string; doc: JokboDoc };

/** 오답노트 표시(2026-11-14). high 틀림 · mid 좁혀서 · low 헷갈림. */
export type JokboBand = "high" | "mid" | "low";

export type JokboMark = {
  itemId: string;
  eventId: string;
  band: JokboBand | null;
  wrongCount: number;
  rightCount: number;
  lastResult: "correct" | "wrong" | "ungraded" | null;
  answeredAt: string | null;
  markedAt: string | null;
};

/** 오답노트 한 줄. 강의를 가리지 않고 모은다(`GET /api/jokbo/wrong-notes`). */
export type JokboNoteEntry = {
  mark: JokboMark;
  lecture: { eventId: string; number: string; title: string; date: string };
  kind: JokboSectionKind;
  professors: string[];
  item: JokboItem;
};

export type JokboNotes = { items: JokboNoteEntry[]; missing: number };
