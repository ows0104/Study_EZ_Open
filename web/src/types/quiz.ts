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

/** 웹 풀이의 갈래. 서버 경로도 이 이름을 그대로 쓴다(`prequiz` / `mainquiz`). */
export type QuizKind = "pre" | "main";

export interface QuizProgress {
  itemCount: number;
  /**
   * 이 편을 한 번이라도 훑은 장수. **오늘 낼 카드 수와 다른 것을 말한다** —
   * 다 훑은 편에도 오늘 낼 카드가 있고, 오늘 낼 것이 없는 편도 안 끝난 것이다.
   * 그래서 서버가 둘을 더하지 않고 나란히 보낸다.
   */
  answered: number;
  correct: number;
  missed: MissedItem[];
  /** 한 번도 안 찍은 카드. */
  new: number;
  /** 익히는 중이고 지금 낼 것. */
  learning: number;
  /** 익었고 지금 낼 것. */
  review: number;
  /** 아직 때가 아닌 것. */
  later: number;
  /** 지금 낼 것 전부 — 위 셋의 합이다. */
  due: number;
  /** 아직 때가 아닌 것 중 가장 이른 때. 없으면 `null`. */
  nextDueAt: string | null;
}

/**
 * 예습 카드 한 장. **보기가 없다** — 자유회상이고 채점은 본인이 한다.
 *
 * `answer`도 `explanation`도 여기 없다. 답을 편 사람만 `reveal`로 받아 가고,
 * 그래야 「맞았다」가 무언가를 뜻한다.
 */
/**
 * 무엇을 눌렀나. **안키의 넷이다**(2026-09-18).
 *
 * 그 전에는 Again과 Pass 둘이었고 카드마다 불리언 하나가 남았다. 지금은 이
 * 넷이 다음 때를 정한다 — 정하는 곳은 서버(`app/srs.py`) 하나다.
 */
export const quizGrades = ["again", "hard", "good", "easy"] as const;

export type QuizGrade = (typeof quizGrades)[number];

/**
 * 카드 한 장의 일정. 서버 `_Attempt`의 칼럼과 같다.
 *
 * `null`이면 아직 안 찍은 카드다 — 그 뜻은 「지금 낸다」이므로 화면이
 * 일정을 계산할 일이 없다.
 */
export type QuizSchedule = {
  /** 본인이 맞았다고 했는가. 넷 중 `again`이면 거짓이다. */
  correct: boolean;
  state: "new" | "learning" | "review" | "relearn";
  step: number;
  /** 익은 카드의 간격. 익히는 중이면 0이다. */
  intervalDays: number;
  ease: number;
  reps: number;
  lapses: number;
  /** 언제 다시 내는가. `null`이면 지금이다. */
  dueAt: string | null;
};

export type QuizItem = {
  itemId: string;
  /** 푸는 방식은 셋 다 같다. 화면이 꼴만 달리 그린다. */
  qtype: "basic" | "cloze" | "ox";
  stem: string;
  focus: string;
  cardType: string;
  examHit: boolean;
  /** 도전 문제 — 수업이 답해 줄 질문. 덱마다 두 장까지. */
  challenge?: boolean;
  /** 「왜 냈나」의 유형 — exam·clinical·later·annotation·basis. 앞면에 배지로 뜬다. */
  whyTags?: string[];
  attempt: QuizSchedule | null;
};

export type QuizPayload = {
  subject: string;
  runId: string;
  title: string;
  items: QuizItem[];
  answered: number;
  correct: number;
  /**
   * 서버의 지금. **화면의 시계를 믿지 않는다** — 익히는 단계는 분 단위라,
   * 기계 시각이 몇 분 틀어져 있으면 「1분 뒤」가 이미 지난 일이 되거나
   * 영영 안 온다. 화면은 이 값으로 차이를 재서 자기 시계를 보정한다.
   */
  now: string;
  /** 되돌릴 것이 있는가. 없으면 버튼을 아예 안 켠다. */
  undoable: boolean;
};

/** 이 버튼을 누르면 언제 다시 나오나. `days`가 0이면 `seconds`를 읽는다. */
export type NextInterval = { days: number; seconds: number };

/**
 * `reveal`이 주는 것. 펴 보기만으로는 아무것도 기록되지 않는다.
 *
 * `next`는 네 버튼에 적을 값이다. **서버가 재서 보낸다** — 화면이 자기
 * 계산으로 적으면 사다리가 파이썬과 타입스크립트 두 곳에 산다.
 */
export type RevealResult = {
  itemId: string;
  answer: string;
  explanation: string;
  /**
   * 왜 이 문제를 냈나 — 예습만(2026-10-04). 앞면에는 유형 배지만 뜨고 이 글은
   * 답을 편 뒤에 온다(관리자 — 「풀고 나서 이유가 보이는 건 어때」). 그 전에
   * 만든 카드·복습 카드·옛 서버는 비거나 없다.
   */
  whyAsked?: string;
  sourceAnchor: string;
  slideNo: number | null;
  slideUrl: string | null;
  next: Record<QuizGrade, NextInterval>;
};

/** `grade`가 돌려주는 것. 찍은 뒤의 일정이라 화면이 큐를 다시 세울 수 있다. */
export type GradeResult = {
  itemId: string;
  grade: QuizGrade;
  correct: boolean;
  attempt: QuizSchedule;
  now: string;
  undoable: boolean;
};

/**
 * `undo`가 돌려주는 것. **답이 펴진 채로 다시 세우는 데 필요한 전부다.**
 *
 * `reveal`을 한 번 더 부르게 두면 누른 뒤에 빈 화면이 한 박자 보인다.
 * `attempt`가 `null`이면 그 찍기가 이 카드의 첫 찍기였다는 뜻이다 — 줄이
 * 사라졌고 카드는 다시 새 카드다.
 */
export type UndoResult = RevealResult & {
  attempt: QuizSchedule | null;
  now: string;
  undoable: boolean;
};
