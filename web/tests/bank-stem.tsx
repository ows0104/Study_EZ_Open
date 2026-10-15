import { useState } from "react";
import { createRoot } from "react-dom/client";
import { BankStem } from "../src/bank/BankStem";
import "../src/styles/base.css";

const comparison = "Clindamycin과 vancomycin을 같은 약동학 기준으로 비교하여 빈칸을 채우시오. 경구흡수: clindamycin은 {{c1}}, vancomycin은 {{c1}}. 세포 내 침투: clindamycin은 {{c1}}, vancomycin은 {{c1}}. 주요 처리 경로: clindamycin은 {{c1}}, vancomycin은 {{c1}}. 신기능 저하 시: clindamycin은 대개 {{c1}}, vancomycin은 {{c1}}.";
const prose = "실험에 참여한 두 집단은 같은 기간 동안 서로 다른 학습 방법을 사용하였으며, 각 집단의 학습 시간과 평가 조건은 동일하게 유지하였다. 첫 번째 집단은 매일 짧게 반복 학습하였고 두 번째 집단은 평가 직전에 한 번에 학습하였다. 일주일 뒤 시행한 평가에서 장기 기억의 차이를 확인하려면 어떤 결과를 비교해야 하는지 설명하시오.";
function Test() {
  const [revealed, setRevealed] = useState(false);
  return <main style={{ maxWidth: 760, margin: "32px auto", padding: 24 }}>
    <p>Advanced · 구별 · 빈칸</p>
    <BankStem text={comparison} cloze answerUnits={revealed ? Array.from({ length: 8 }, (_, i) => `예시 답 ${i + 1}`) : undefined} />
    <button style={{ marginTop: 20 }} onClick={() => setRevealed(!revealed)}>{revealed ? "다시 풀기" : "정답 표시 확인"}</button>
    <hr style={{ margin: "32px 0" }} />
    <p>긴 발문</p><BankStem text={prose} />
  </main>;
}
createRoot(document.getElementById("root")!).render(<Test />);
