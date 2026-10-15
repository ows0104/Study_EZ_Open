import type { BankCoverage as Coverage } from "../types/bank";

/** 형식 검사 통과를 원본 누락 검증으로 표시하지 않는다. */
export function BankCoverage({ value }: { value?: Coverage | null }) {
  if (!value) return <p className="bank-note">원본 대조 전 · 현재 카드의 개념 누락은 아직 확인하지 않았습니다.</p>;
  if (value.status === "stale") return <p className="bank-note">문항이 변경돼 원본 대조를 다시 해야 합니다.</p>;
  return <details className="bank-session-details">
    <summary>{value.status === "verified" ? typeof value.pointCount === "number" ? "출제 포인트 대조 완료" : "이전 원본 대조 결과 · 포인트 선행 추출 검증 전" : "원본 대조 · 확인할 부분이 남았습니다"}
      {` · 누락 의심 ${value.gapCount}개 · 읽지 못한 쪽 ${value.unreadablePages}개`}</summary>
    <p>{value.totalPages}쪽 중 출제 범위 {value.checkedPages}쪽 대조 · 범위 밖·표지 등 {value.excludedPages}쪽 제외</p>
    {typeof value.pointCount === "number" ? <p>원본에서 먼저 추출한 출제 포인트 {value.pointCount}개 중 {value.coveredPointCount}개를 실제 문항으로 확인했습니다.</p> : <p>새 방식으로 확인하려면 누락 검증·객관식 보강을 다시 요청하세요.</p>}
    <p>보강 {value.addedQuestions}문항 · 그중 객관식 {value.addedMcq}문항</p>
    {value.classification?.status === "verified" ? <p>객관식 {value.classification.classifiedCount}문항 유형 확인 · 기억 확인형 {value.classification.recallFirstCount}문항 · 구별·판단형 {value.classification.comparisonCount}문항</p> : null}
    {value.issues?.length ? <ul>{value.issues.map(issue => <li key={issue.page}>
      p.{issue.page} · {[...issue.facts, issue.note].filter(Boolean).join(" · ")}
    </li>)}</ul> : null}
    <p className="bank-note">PDF의 사실과 실제 문항을 AI로 대조한 결과입니다. 모든 개념이 빠짐없이 들어 있다는 보증은 아닙니다.</p>
  </details>;
}
