// Non-medical fixture for explanations in the real components.
import { useState } from "react";
import { createRoot } from "react-dom/client";
import { AnswerBody, QuestionBody } from "../src/bank/BankQuestion";
import type { BankAnswer, BankQuestion } from "../src/types/bank";
import "../src/styles/base.css";

const question: BankQuestion = {
  question_id: "fixture-hint", concept_id: "fixture", tier: "Core", importance: 4,
  format: "cloze", retrieval_direction: "mechanism", mcq_mode: "none",
  question: "관계 예시: {{c1}}에서 {{c1}}로 {{c1}}.",
  source_refs: [], conflict_id: "",
  options: [], matching_left: [], matching_right: [], sequence_items: [],
};
const answer: BankAnswer = {
  answer: "관계 예시: A에서 B로 이동.", answerUnits: ["A", "B", "이동"],
  explanation: "시작점은 A, 도착점은 B이며 과정은 이동입니다.",
  answerPairs: [], correctOrder: [], correctOptionIds: [], slides: [], medicalReview: null,
};
function Test() {
  const [revealed, setRevealed] = useState(false);
  return <main style={{ maxWidth: 720, margin: "32px auto", padding: 24 }}>
    <h1>문항 해설 테스트</h1>
    <p>의학 내용 없이 실제 문항 표시 컴포넌트를 확인합니다.</p>
    <QuestionBody question={question} answer={revealed ? answer : null} picked={new Set()} onPick={() => {}} />
    {revealed ? <AnswerBody question={question} answer={answer} /> : null}
    <button onClick={() => setRevealed(!revealed)}>{revealed ? "다시 풀기" : "정답 보기"}</button>
  </main>;
}
createRoot(document.getElementById("root")!).render(<Test />);
