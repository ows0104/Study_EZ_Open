import { createRoot } from "react-dom/client";
import { AnswerBody } from "../src/bank/BankQuestion";
import type { BankAnswer, BankQuestion } from "../src/types/bank";
import "../src/styles/base.css";

const question: BankQuestion = { question_id: "readable", concept_id: "fixture", tier: "Core", importance: 4,
  format: "list", retrieval_direction: "direct", mcq_mode: "none", question: "학습 결과의 차이를 설명하시오.",
  source_refs: [], conflict_id: "", options: [], matching_left: [], matching_right: [], sequence_items: [] };
const answer: BankAnswer = {
  answer: "반복 학습은 여러 시점에 걸쳐 내용을 다시 떠올리며 기억을 확인하는 방법으로, 한 번에 많은 내용을 읽는 학습과 구별된다. 내용을 다시 떠올리는 과정에서 기억이 불확실한 부분을 발견하고 다음 학습에서 무엇을 확인해야 할지 판단할 수 있다. 따라서 평가 결과를 비교할 때에는 총 학습 시간뿐 아니라 학습 사이의 간격과 기억을 평가한 시점도 함께 확인해야 한다.",
  answerUnits: ["반복 학습", "학습 사이의 간격", "기억을 평가한 시점"],
  explanation: "두 집단이 같은 시간 동안 학습하였더라도 학습을 배치한 방식에 따라 평가 시점의 결과가 달라질 수 있으므로, 한 번의 점수만으로 학습 방법을 판단하기는 어렵다. 학습 직후의 평가와 일정한 시간이 지난 뒤의 평가를 구분하면, 단기적인 수행과 장기적인 기억을 각각 살펴볼 수 있다. 비교 조건이 달라지지 않았는지 확인하면서 결과를 해석해야 한다.",
  answerPairs: [], correctOrder: [], correctOptionIds: [], slides: [], medicalReview: null,
};
createRoot(document.getElementById("root")!).render(<main style={{ width: "min(100%, 760px)", margin: "24px auto", padding: 20 }}>
  <h1>긴 정답과 해설</h1><AnswerBody question={question} answer={answer} />
</main>);
