import { useState } from "react";
import { createRoot } from "react-dom/client";
import { AnswerBody } from "../src/bank/BankQuestion";
import type { BankAnswer, BankQuestion } from "../src/types/bank";
import "../src/styles/base.css";

const question: BankQuestion = {
  question_id: "slides-1", concept_id: "fixture", tier: "Core", importance: 4,
  format: "basic", retrieval_direction: "direct", question: "예시 관계를 설명하시오.",
  source_refs: [], conflict_id: "", options: [], matching_left: [], matching_right: [], sequence_items: [],
};
const answer: BankAnswer = {
  answer: "A와 B의 관계", answerUnits: ["A와 B의 관계"], answerPairs: [], correctOrder: [],
  correctOptionIds: [], medicalReview: null,
  slides: [1, 3, 4, 8].map(page => ({
    page, primary: page === 8,
    url: `data:image/svg+xml,${encodeURIComponent(`<svg xmlns="http://www.w3.org/2000/svg" width="900" height="420"><rect width="900" height="420" fill="#f1f5fb"/><text x="48" y="90" font-size="36" fill="#28456a">Reference slide ${page}</text><path d="M48 130H850" stroke="#bbc9dc"/><text x="48" y="200" font-size="22" fill="#526781">Example source material</text></svg>`)}`,
  })),
  jokboSlides: [{ page: 12, pdfFilename: "예시 족보.pdf", references: ["2023 52번"],
    url: `data:image/svg+xml,${encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="900" height="760"><rect width="900" height="760" fill="#fffef9"/><text x="48" y="90" font-size="36" fill="#5f4c2f">Past exam - original PDF page 12</text><path d="M48 130H850" stroke="#c8bda6"/><text x="48" y="200" font-size="22" fill="#72664f">2023 / Question 52</text></svg>')}` }],
};
function Test() {
  const [number, setNumber] = useState(1);
  return <main style={{ maxWidth: 780, margin: "32px auto", padding: 24 }}>
    <h1>참고 슬라이드 · 문제 {number}</h1>
    <AnswerBody question={{ ...question, question_id: `slides-${number}` }} answer={answer} />
    <button onClick={() => setNumber(value => value + 1)}>다음 문제</button>
  </main>;
}
createRoot(document.getElementById("root")!).render(<Test />);
