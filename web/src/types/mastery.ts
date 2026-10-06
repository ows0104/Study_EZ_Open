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
