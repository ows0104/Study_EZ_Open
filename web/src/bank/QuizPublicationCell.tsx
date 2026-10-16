import type { QuizPublication } from "./useQuizPublication";

const time = (value: string) => new Intl.DateTimeFormat("ko-KR", { timeZone: "Asia/Seoul", month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit", hourCycle: "h23" }).format(new Date(value));

export function QuizPublicationCell({ value, kind, applicable = true }: { value?: QuizPublication; kind: "link" | "upload"; applicable?: boolean }) {
  if (!applicable) return <td className="quiz-production">—</td>;
  if (!value) return <td className="quiz-production"><span>확인 중</span></td>;
  if (kind === "link") {
    const labels = { complete: value.link.sinceCutoff ? "완료" : "10/15 이전 응답", incomplete: "미완성", wrong_lecture: "다른 강의 링크",
      unavailable: "공유 확인 실패", unsupported: "확인 필요", unchecked: "확인 대기", missing: "링크 없음" };
    const ok = value.link.sinceCutoff;
    return <td className={`quiz-production ${ok ? "is-complete" : "is-incomplete"}`}>
      {value.shareUrl ? <a href={value.shareUrl} target="_blank" rel="noreferrer">{ok ? "✓ " : ""}{labels[value.link.state]} ↗</a> : <span>{labels[value.link.state]}</span>}
      {value.link.completedAt ? <small>응답 {time(value.link.completedAt)}</small> : null}
      {value.link.state === "complete" ? <small>{value.link.questionCount}문항</small> : null}
      {value.link.checkedAt ? <small title="공개 공유 페이지를 마지막으로 확인한 시각">확인 {time(value.link.checkedAt)}</small> : null}
    </td>;
  }
  const active = value.job && ["running", "queued", "held"].includes(value.job.state);
  const label = value.upload.current ? "완료" : value.upload.sinceCutoff ? "새 응답 미반영" : value.upload.builtAt ? "10/15 이전 업로드" : "미업로드";
  return <td className={`quiz-production ${value.upload.current ? "is-complete" : "is-incomplete"}`}>
    <span>{value.upload.current ? "✓ " : ""}{label}</span>
    {value.upload.builtAt ? <small>업로드 {time(value.upload.builtAt)}</small> : null}
    {active ? <small role="status">{value.job!.state === "running" ? value.job!.stage || "처리 중" : value.job!.state === "held" ? "보류" : "러너 대기"}</small>
      : value.job?.state === "failed" && !value.upload.current ? <small>검수·처리 실패</small> : null}
  </td>;
}
