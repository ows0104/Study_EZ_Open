import type { BankAnswer } from "../types/bank";
const titles = {
  partial_support: "근거 일부 부족",
  source_conflict: "자료 충돌",
  unsupported: "근거 미확인",
  uncertain: "근거 판정 어려움",
};

export function BankEvidenceNotice({ status }: { status: BankAnswer["evidenceStatus"] }) {
  if (!status) return null;
  if (status.category === "exam_only") {
    return <p className="bank-note" role="note">강의 본문에서 핵심 근거를 확인하지 못해 족보 지면을 근거로 제시합니다.
      {status.primaryAvailable === false ? " 핵심 족보 지면을 아직 표시할 수 없습니다." : ""}</p>;
  }
  return <section className="bank-evidence-notice" aria-label={titles[status.category]} role="note">
    <h2>{titles[status.category]}</h2>
    <p>{status.reason}</p>
    {status.missingClaim ? <p><b>확인되지 않은 핵심</b> {status.missingClaim}</p> : null}
  </section>;
}
