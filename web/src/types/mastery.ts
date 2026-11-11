export type CardProgress = {
  total: number;
  seen: number;
  unseen: number;
  recognized: number;
  retrieving: number;
  retained: number;
  newRemaining: number;
  reviewDue: number;
  suspended: number;
};

/** 사이트 학습률(2026-11-11): Main-Quiz 하나. 서버 `root_learning/score.py` → `lecture_mastery.as_mastery`. */
export type MainQuizRate = {
  status: "not_started" | "needs_review" | "mastered";
  score: number;
  scope: "main-quiz";
  /** 지도 목표 수 */
  targetCount: number;
  /** 목표치에 닿은 지도 목표 수 */
  fullTargets: number;
  /** 한 번이라도 평가한 지도 목표 수 */
  ratedTargets: number;
};

/** Legacy Quiz Bank 학습도. `?legacy=1` 은행 화면에서만 쓴다. */
export type LectureMastery = {
  status: "not_started" | "needs_review" | "mastered";
  score: number;
  scope: "core" | "all";
  conceptCount: number;
  masteredConcepts: number;
  weakConcepts: number;
  assessedDirections: number;
  totalDirections: number;
  weakest: { conceptId: string; title: string }[];
};
