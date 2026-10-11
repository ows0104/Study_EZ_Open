export type LearningProgress = { total: number; covered: number; delayedRecall: number; questionGaps: number; legacyObjectives: number };
export type LearningDashboard = {
  enabled: boolean; minutes: number; bufferDays: number; progress: LearningProgress;
  missingLectures: { title: string; date: string }[]; uncertainRanges: number;
  scopeOnlyLectures?: { subject: string; runId: string; title: string;
    ranges: { title: string; status: string; reason: string; source_refs: SourceRef[] }[] }[];
  activeSession: string | null; examQuestions: number;
  plan: { budgetSeconds: number; estimatedSeconds: number; activeSeconds: number; remaining: number;
    complete: boolean; completed: string[]; entries: { key: string; lane: string; seconds: number }[];
    infeasible: boolean; newRequiredMinutes: number; revision: number };
  lectures: (LearningProgress & { subject: string; runId: string; title: string })[];
  objectives: { key: string; title: string; lecture: string; subject: string; runId: string; kind: string;
    sourceRefs: SourceRef[]; covered: boolean; related: string[] }[];
};
export type SourceRef = { source_id: string; locator: string };
export type LearningQuestion = {
  question_id: string; concept_id: string; format: string; question: string;
  options: { id: string; text: string }[]; matching_left: string[]; matching_right: string[];
  sequence_items: string[]; source_refs: SourceRef[];
};
export type LearningAnswer = { selected?: string[]; text?: string; pairs?: Record<string, string>; order?: string[] };
export type LearningFeedback = {
  answer?: string; answerUnits?: string[]; correctOptionIds?: string[];
  answerPairs?: { left: string; right: string }[]; correctOrder?: string[];
  optionExplanations?: { option_id: string; text: string }[];
  sourceRefs?: SourceRef[]; correct?: boolean | null; confidence?: string;
  explanation: string; minimum: string;
  medicalReview?: { verdict: string; note: string; suggested_answer: string } | null; sourceConflict?: string;
};
export type LearningSession = {
  sessionId: string; mode: "daily" | "extra" | "exam"; status: "active" | "complete";
  index: number; total: number; seconds: number; activeSeconds?: number; canUndo: boolean;
  token?: string; lane?: string; lecture?: string; subject?: string; runId?: string;
  optionsShown?: boolean; assisted?: boolean; submitted?: boolean;
  question?: LearningQuestion | null; recallPrompt?: string; objective?: string;
  help?: { context: string; explanation: string; minimum: string; rationale: string; source_refs: SourceRef[] } | null;
  feedback?: LearningFeedback | null; submittedAnswer?: LearningAnswer | null;
  summary?: { completed: number; graded: number; correct: number; freshGraded: number; freshCorrect: number;
    newObjectives: number; delayedRecall: number; burden: string | null };
  results?: (LearningFeedback & { title: string; question: LearningQuestion; submittedAnswer: LearningAnswer })[];
};
