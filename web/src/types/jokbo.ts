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
