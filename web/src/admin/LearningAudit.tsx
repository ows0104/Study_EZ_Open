import { useEffect, useState } from "react";
import { api } from "../api";
import { Stem } from "../lecture/Stem";
import "../styles/learning.css";

type Audit = { bank: {
  build_meta?: { schema_version: string };
  coverage_inventory?: { title: string; status: string; reason: string; source_refs: { source_id: string; locator: string }[]; objective_ids: string[] }[];
  learning_objectives?: { objective_id: string; title: string; target: string; kind: string; context: string; explanation: string; minimum: string; rationale: string }[];
  questions: { question_id: string; primary_objective_id?: string; role?: string; recall_prompt?: string; format?: string }[];
  exam_design?: { question_id: string; basis_refs: { source_id: string; locator: string }[]; changed_dimension: string; novelty: string }[];
} | null; validation?: { errors?: string[]; warnings?: string[] } };
const STATUS: Record<string, string> = { target: "학습 대상", explanation: "이해 설명", excluded: "범위 제외", uncertain: "검토 필요" };

export function LearningAudit({ subject, runId }: { subject: string; runId: string }) {
  const [data, setData] = useState<Audit | null>(null);
  const [error, setError] = useState("");
  useEffect(() => { let active = true;
    api<Audit>(`/api/admin/lectures/${encodeURIComponent(subject)}/${encodeURIComponent(runId)}/bank`)
      .then(d => { if (active) setData(d); }).catch(e => { if (active) setError(e.message); });
    return () => { active = false; };
  }, [subject, runId]);
  return <details className="learning-panel"><summary>원본 범위와 학습요점 검토</summary>
    {error ? <p role="alert">{error}</p> : null}
    {data && !data.bank ? <p>문제은행이 아직 준비되지 않았습니다.</p> : null}
    {data?.bank && !data.bank.learning_objectives?.length ? <p>{["4.0", "4.1"].includes(data.bank.build_meta?.schema_version ?? "")
      ? "등록된 학습 대상 요점이 없습니다. 아래 범위 제외 근거와 검토 필요 항목을 확인하세요."
      : "기존 은행입니다. 전체 범위 목록이 없으므로 문항 수만으로 원본 누락 여부를 판단하지 않습니다."}</p> : null}
    {data?.bank ? <p>객관식 배치 · 대표 학습 {data.bank.questions.filter(q => q.role === "learning" && ["mcq", "multi_select"].includes(q.format ?? "")).length}
      개 · 복습 변형 {data.bank.questions.filter(q => q.role === "variant" && ["mcq", "multi_select"].includes(q.format ?? "")).length}
      개 · 시험 {data.bank.questions.filter(q => q.role === "exam").length}개</p> : null}
    {data?.bank?.coverage_inventory?.map((c, i) => <article key={i}><h4>{STATUS[c.status]} · {c.title}</h4><p>{c.reason}</p>
      <small>{c.source_refs.map(r => `${r.source_id} ${r.locator}`).join(" · ")} · {c.objective_ids.join(", ")}</small></article>)}
    {data?.bank?.learning_objectives?.map(o => {
      const qs = data.bank!.questions.filter(q => q.primary_objective_id === o.objective_id);
      return <details key={o.objective_id}><summary>{o.objective_id} · {o.title}{!qs.some(q => q.role !== "exam") ? " · 학습 문항 미준비" : ""}</summary>
        <p><b>목표</b> <Stem text={o.target} /></p><p>{o.context}</p><p><Stem text={o.explanation} /></p>
        <p><b>최소 기억 내용</b> <Stem text={o.minimum} /></p><p>{o.rationale}</p>
        <ul>{qs.map(q => <li key={q.question_id}>{q.question_id} · {q.role} {q.recall_prompt ? `· 보기 전 질문: ${q.recall_prompt}` : ""}</li>)}</ul>
      </details>;
    })}
    {data?.bank?.exam_design?.length ? <details><summary>시험 문항의 새로운 판단 근거</summary>
      <p>출제자가 기록한 근거입니다. 원본 기출과 직접 대조해 새 문항인지 확인하세요.</p>
      {data.bank.exam_design.map(d => <article key={d.question_id}><h4>{d.question_id} · {d.changed_dimension}</h4>
        <p><Stem text={d.novelty} /></p><small>{d.basis_refs.map(r => `${r.source_id} ${r.locator}`).join(" · ") || "대응하는 원본 기출 없음"}</small></article>)}
    </details> : null}
    {data?.validation?.errors?.length ? <ul role="alert">{data.validation.errors.map((e, i) => <li key={i}>{e}</li>)}</ul> : null}
    {data?.validation?.warnings?.length ? <ul>{data.validation.warnings.map((w, i) => <li key={i}>{w}</li>)}</ul> : null}
  </details>;
}
