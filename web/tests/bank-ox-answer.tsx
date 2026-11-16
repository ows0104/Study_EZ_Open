import { createRoot } from "react-dom/client";
import { AnswerBody } from "../src/bank/BankQuestion";
import type { BankAnswer, BankQuestion } from "../src/types/bank";
import "../src/styles/base.css";
import "../src/bank/source-notes.css";

// OX 정답 줄 「X: 이유」(2026-11-16). 콜레라 편 OX 문항의 실제 문장.
const q = (id: string, stem: string): BankQuestion => ({ question_id: id, concept_id: "fixture", tier: "Core", importance: 4,
  format: "ox", retrieval_direction: "trap", mcq_mode: "none", question: stem,
  source_refs: [], conflict_id: "", options: [], matching_left: [], matching_right: [], sequence_items: [] });
const a = (mark: string, explanation: string, units = [mark]): BankAnswer => ({ answer: mark, answerUnits: units, explanation,
  answerPairs: [], correctOrder: [], correctOptionIds: [], slides: [], medicalReview: null });
const items: [BankQuestion, BankAnswer][] = [
  [q("Q015", "V. cholerae O1은 전형적인 다당류 협막을 형성한다."), a("X", "O1은 전형적인 다당류 협막을 형성하지 않는다. V. vulnificus·O139 및 일부 non-O1 균주는 협막이 침습성·식균회피에 기여한다.")],
  [q("Q999", "CagA는 H. pylori가 가진 독성인자다."), a("O", "CagA는 **H. pylori**의 것이다. Campylobacter의 독소는 CDT다.")],
  [q("Q103", "표준 감수성검사에서 감수성이면 생물막 감염에서도 동일한 살균 효과를 보장한다."), a("X", "표준 검사는 생물막·감염 부위·약물 도달·숙주 상태를 모두 재현하지 못한다. 약제 선택에는 여전히 필수적이다. 생물막 안에서는 대사가 느린 세포와 기질이 약물 작용을 줄여, 시험관에서 감수성이어도 실제 살균 효과는 떨어질 수 있다.")],
  [q("LEGACY", "옛 은행: 이유가 채점 단위에만 있다."), a("X", "", ["X", "근거는 **키워드**다."])],
];
createRoot(document.getElementById("root")!).render(<main style={{ width: "min(100%, 760px)", margin: "24px auto", padding: 20 }}>
  {items.map(([question, answer]) => <section key={question.question_id} style={{ borderBottom: "1px solid #ddd", padding: "12px 0" }}>
    <p>{question.question}</p><AnswerBody question={question} answer={answer} />
  </section>)}
</main>);
