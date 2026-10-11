import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { LectureWorkload, learningDate, learningUnit, workloadOf } from "./LearningWorkload";
import { SourceRefs } from "./LearningFeedback";
import type { LearningDashboard as Dashboard } from "../types/learning";

export function LearningDashboard({ dashboard: d, scoped, subject, runId, busy, start, resume, saveSettings }: {
  dashboard: Dashboard; scoped: boolean; subject?: string; runId?: string; busy: boolean;
  start: (mode: "daily" | "extra" | "exam") => void; resume: () => void;
  saveSettings: (minutes: number, buffer: number, replan: boolean) => void;
}) {
  const [minutes, setMinutes] = useState(d.minutes), [buffer, setBuffer] = useState(d.bufferDays);
  const [search, setSearch] = useState(""), [settingsOpen, setSettingsOpen] = useState(false);
  const settingsRef = useRef<HTMLDetailsElement>(null);
  useEffect(() => { setMinutes(d.minutes); setBuffer(d.bufferDays); }, [d.minutes, d.bufferDays]);
  useEffect(() => { if (settingsOpen) settingsRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" }); }, [settingsOpen]);
  const p = d.progress, w = d.workload ?? workloadOf(p), unit = learningUnit(p), t = w.today;
  const timeReached = d.plan.activeSeconds >= d.plan.budgetSeconds;
  const daily = !d.plan.complete && !timeReached && d.plan.remaining > 0;
  const hasContent = p.total > 0;
  const settingsValid = Number.isInteger(minutes) && minutes >= 5 && minutes <= 480
    && Number.isInteger(buffer) && buffer >= 0 && buffer <= 14;
  const sourceOnly = Boolean(d.scopeOnlyLectures?.length);
  const lecture = subject && runId ? `/lectures/${encodeURIComponent(subject)}/${encodeURIComponent(runId)}` : null;
  const legacy = subject && runId ? `/bank/${encodeURIComponent(subject)}/${encodeURIComponent(runId)}?classic=1` : null;
  return <>
    <div className="learning-dashboard-top">
      <section className="learning-goal-card" aria-label={scoped ? "이 강의 공부 현황" : "전체 공부 현황"}>
        <h2>{scoped ? "이 강의에서 한 번 공부한 범위" : "전체 강의에서 한 번 공부한 범위"}</h2>
        {hasContent ? <>
          <p className="learning-goal-number"><strong>{p.covered}</strong><span>/ {p.total}{unit}</span></p>
          <progress aria-label="공부한 범위" value={p.covered} max={p.total} />
          <div className="learning-remaining-counts"><div><span>처음 공부할</span><strong>{w.unseen}<small>{unit}</small></strong></div>
            <div><span>다시 복습할</span><strong>{d.workload ? <>{w.dueReviews}<small>{unit}</small></> : "확인 중"}</strong></div></div>
          <p className="learning-goal-date">{w.firstPassTargetAt ? `전 범위 공부 목표 ${learningDate(w.firstPassTargetAt)}` : "목표: 전체 범위를 한 번씩 공부하기"}{w.examAt ? ` · 시험 ${learningDate(w.examAt)}` : ""}</p>
          {w.nextReviewAt ? <small className="learning-muted">다음 복습 {learningDate(w.nextReviewAt)}</small> : null}
        </> : <p className="learning-empty-goal">{sourceOnly ? "등록된 학습 대상이 없어요" : "공부할 자료를 준비하고 있어요"}</p>}
      </section>
      <section className="learning-today-card" aria-label={scoped ? "오늘 이 강의에서 할 공부" : "오늘 할 공부"}>
        <h2>{scoped ? "오늘 이 강의에서 풀 분량" : "오늘 풀 분량"}</h2>
        <p className="learning-today-number">{!hasContent ? sourceOnly ? "이 강의는 풀 분량이 없어요" : "자료 준비 중" : !t ? "오늘 분량 확인 중" : t.remaining ? <><strong>{t.remaining}개</strong> 남았어요</>
          : t?.deferred || (timeReached && d.plan.completed.length < d.plan.entries.length) ? "오늘 공부 시간을 채웠어요"
          : t?.total ? "오늘 분량을 마쳤어요" : "오늘 배정된 분량이 없어요"}</p>
        {t?.remaining ? <p className="learning-today-breakdown">처음 공부 {t.new}개 <span>·</span> 복습 {t.review}개</p> : null}
        {t?.total ? <p className="learning-muted">오늘 {t.completed} / {t.total}개 완료{t.deferred ? ` · 미완료 ${t.deferred}개 남음` : ""}</p> : null}
        {d.activeSession ? <><button className="primary learning-start-button" disabled={busy} onClick={resume}>이어서 풀기 →</button><p className="learning-action-hint">{d.activeSessionInfo ? `진행 중: ${d.activeSessionInfo.lecture}` : "중단한 문제로 돌아갑니다."}</p></>
          : !d.enabled && hasContent ? <button className="primary learning-start-button" disabled={busy} onClick={() => saveSettings(d.minutes, d.bufferDays, false)}>학습 켜기</button>
          : daily && hasContent ? <button className="primary learning-start-button" disabled={busy} onClick={() => start("daily")}>오늘 분량 {d.plan.remaining}개 풀기 →</button>
          : hasContent && scoped ? <button className="primary learning-start-button" disabled={busy} onClick={() => start("extra")}>{w.unseen ? "이 강의 공부 시작" : "이 강의 다시 풀기"} →</button>
          : hasContent ? <a className="learning-start-link" href="#learning-lectures">강의 골라서 공부하기 ↓</a> : null}
        {!d.activeSession && d.enabled && hasContent ? <div className="learning-other-actions">
          {daily && scoped ? <button disabled={busy} onClick={() => start("extra")}>오늘 분량 외에 더 풀기</button> : null}
          {d.examQuestions > 0 ? <div><button disabled={busy} onClick={() => start("exam")}>시험처럼 풀기</button><small>처음 보는 객관식 · 끝난 뒤 정답 확인</small></div> : null}
        </div> : null}
        {!scoped && d.plan.infeasible ? <p className="learning-plan-note">목표일까지 전체 범위를 공부하려면 계획 조정이 필요해요. <button onClick={() => setSettingsOpen(true)}>계획 조정</button></p> : null}
      </section>
    </div>
    {scoped && lecture ? <nav className="learning-material-links" aria-label="이 강의 자료"><Link to={lecture}>강의록·자료 보기 ↗</Link>{legacy ? <Link to={legacy}>이전 방식으로 풀기 →</Link> : null}</nav> : null}
    {!scoped ? <LectureWorkload lectures={d.lectures} /> : null}
    <div className="learning-dashboard-details">
      <details ref={settingsRef} className="learning-panel" open={settingsOpen} onToggle={e => setSettingsOpen(e.currentTarget.open)}><summary>공부 계획 설정</summary>
        <div className="learning-settings"><label>하루 공부 시간 <input type="number" min={5} max={480} value={minutes} onChange={e => setMinutes(Number(e.target.value))} /> 분</label>
          <label>전체 범위를 시험 <input type="number" min={0} max={14} value={buffer} onChange={e => setBuffer(Number(e.target.value))} /> 일 전까지 한 번 공부하기</label></div>
        <p className="learning-muted">하루 공부 시간은 모든 강의가 함께 사용합니다.</p>
        {d.plan.infeasible ? <p className="learning-plan-note">현재 목표일까지 전체 강의의 새 내용을 공부하려면 하루 약 {d.plan.newRequiredMinutes}분이 필요해요.</p> : null}
        {d.activeSession ? <p className="learning-muted">진행 중인 공부를 마친 뒤 오늘 분량을 바꿀 수 있어요.</p> : null}
        <div className="learning-actions"><button disabled={busy || !settingsValid || Boolean(d.activeSession)} onClick={() => saveSettings(minutes, buffer, true)}>오늘 남은 분량 다시 계산</button>
          <button disabled={busy || !settingsValid} onClick={() => saveSettings(minutes, buffer, false)}>내일부터 적용</button></div>
      </details>
      <details className="learning-panel"><summary>공부할 내용 찾아보기</summary><label>내용 검색 <input value={search} onChange={e => setSearch(e.target.value)} placeholder="개념이나 강의 이름" /></label>
        <ul className="learning-objectives">{d.objectives.filter(o => `${o.title} ${o.lecture}`.toLocaleLowerCase().includes(search.toLocaleLowerCase())).slice(0, 100).map(o => <li key={o.key}>
          <strong>{o.covered ? "✓ " : "○ "}{o.title}</strong>{!scoped ? <p>{o.lecture}</p> : null}<SourceRefs refs={o.sourceRefs} />
          {o.related.length ? <p>먼저 공부할 내용: {o.related.map(k => d.objectives.find(x => x.key === k)?.title).filter(Boolean).join(" · ")}</p> : null}</li>)}</ul>
        <small className="learning-muted">검색 결과는 최대 100개까지 표시합니다.</small></details>
      {(!scoped && (d.missingLectures.length || d.uncertainRanges)) || p.questionGaps || sourceOnly ? <details className="learning-panel"><summary>자료 준비 현황</summary>
        {!scoped && d.missingLectures.length ? <><p>학습 자료 준비 중인 강의 {d.missingLectures.length}개</p><ul>{d.missingLectures.map((l, i) => <li key={i}>{l.date} · {l.title}</li>)}</ul></> : null}
        {!scoped && d.uncertainRanges ? <p>공부할 범위 확인 중 {d.uncertainRanges}개</p> : null}
        {p.questionGaps ? <p>{p.questionGaps}{unit}은 문제 대신 설명으로 공부합니다.</p> : null}
        {d.scopeOnlyLectures?.map(l => <details key={`${l.subject}/${l.runId}`}><summary>{l.title} · 학습 대상 없음</summary>{l.ranges.map((r, i) => <p key={i}>{r.title} · {r.reason}<br /><SourceRefs refs={r.source_refs} /></p>)}
          <Link to={`/lectures/${encodeURIComponent(l.subject)}/${encodeURIComponent(l.runId)}`}>강의 자료 보기</Link></details>)}
      </details> : null}
    </div>
    <footer className="learning-dashboard-help"><Link to="/guide#learning">학습 방법·숫자 집계 기준</Link><span>준비된 자료에서 정답·해설을 확인하고 평가한 범위를 셉니다.</span></footer>
  </>;
}
