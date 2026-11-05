import React, { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { bundles, REVISION, type Bundle, type Prompt } from './data';
import { decodeSession, freshSession, reduceSession, STORAGE_KEY, summarize, type Action, type Session, type Step } from './state';
import './pilot.css';

function initial(): { session: Session; warning: string; blocked: boolean } {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return { session: raw ? decodeSession(raw) : freshSession(), warning: '', blocked: false };
  } catch {
    return { session: freshSession(), warning: '저장된 기록을 읽을 수 없어 임시로 시작했어요. 기존 기록을 덮어쓰지 않습니다. 결과를 내려받아 보관하세요.', blocked: true };
  }
}
const markLabels = { recalled: '떠올렸음', partial: '일부만', learned: '새로 배움' } as const;

function PromptCard({ prompt, step, onAction, id, name }: { prompt: Prompt; step: Step; onAction: (a: Action) => void; id: string; name: 'root' | 'follow' }) {
  const label = name === 'root' ? '먼저 연결 떠올리기' : '세부로 이어가기';
  return <section className="question-card" aria-labelledby={`${id}-${name}-title`}>
    <div className="eyebrow">{name === 'root' ? '01' : '02'} / {label}</div>
    <h2 id={`${id}-${name}-title`}>{prompt.question}</h2>
    <label className="response-label" htmlFor={`${id}-${name}-response`}>내가 떠올린 답 <span>짧은 단어로 적어도 좋아요 · 선택 입력</span></label>
    <textarea id={`${id}-${name}-response`} value={step.response} readOnly={step.revealed} maxLength={10000} placeholder="떠오르는 연결을 적어보세요. 모르면 비워두고 설명으로 넘어가도 괜찮아요." onChange={e => onAction({ type: 'response', id, step: name, value: e.target.value })} />
    {!step.revealed ? <button className="primary" onClick={() => onAction({ type: 'reveal', id, step: name })}>{step.response.trim() ? '답과 비교하기' : '답·설명 보기'}</button> : <div className="answer-panel">
      <h3>답과 비교해보세요</h3>
      <p className="muted">정답 자동 채점이 아닙니다. 답을 보기 전에 떠올렸던 항목을 표시하세요.</p>
      {prompt.answers.map((answer, index) => <div className="answer-row" key={answer}>
        <p>{answer}</p>
        <fieldset><legend className="sr-only">{answer} 자기확인</legend>
          {Object.entries(markLabels).map(([value, text]) => <label className={`mark ${step.marks[index] === value ? 'selected' : ''}`} key={value}>
            <input type="radio" name={`${id}-${name}-${index}`} checked={step.marks[index] === value} onChange={() => onAction({ type: 'mark', id, step: name, index, value: value as keyof typeof markLabels })} />{text}
          </label>)}
          {step.marks[index] && <button className="text-button" onClick={() => onAction({ type: 'mark', id, step: name, index, value: '' })}>표시 해제</button>}
        </fieldset>
      </div>)}
      <div className="explanation"><strong>연결 설명</strong><p>{prompt.explanation}</p></div>
    </div>}
  </section>;
}

function Evidence({ b }: { b: Bundle }) {
  return <dl className="evidence">
    <dt>질문 형태</dt><dd>{b.type}</dd><dt>구조적 역할</dt><dd>{b.structure}</dd><dt>학습 역할</dt><dd>{b.role}</dd>
    <dt>실제 확인할 연결</dt><dd>{b.connection}</dd><dt>출처</dt><dd>{b.sources} · 초안 {b.original}</dd>
    <dt>이해의 뼈대</dt><dd>{b.structural}</dd><dt>시험 근거</dt><dd>{b.exam}</dd><dt>임상 근거</dt><dd>{b.clinical}</dd>
    <dt>남은 질문·검토</dt><dd>{b.gap}</dd>
  </dl>;
}

function App() {
  const [boot] = useState(initial);
  const [session, setSession] = useState(boot.session);
  const [warning, setWarning] = useState(boot.warning);
  const [storageBlocked, setStorageBlocked] = useState(boot.blocked);
  const [tab, setTab] = useState<'learn' | 'review' | 'results'>('learn');
  const [notice, setNotice] = useState('');
  const [resetPending, setResetPending] = useState(false);
  const dispatch = (a: Action) => setSession(s => reduceSession(s, a));
  useEffect(() => {
    if (storageBlocked) return;
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(session)); }
    catch { setWarning('이 브라우저에 저장하지 못했어요. 창을 닫기 전에 결과를 내려받아 주세요.'); }
  }, [session, storageBlocked]);
  const stats = summarize(session);
  const b = bundles[session.current], entry = session.entries[b.id];
  function navigate(index: number) { dispatch({ type: 'select', index }); setTab('learn'); window.scrollTo({ top: 0, behavior: 'smooth' }); }
  function download() {
    const payload = { exportedAt: new Date().toISOString(), revision: REVISION, scope: '첫 10묶음 시범·자기확인, 강의 전체 완료나 독립 회상 인증 아님', summary: stats, session,
      questions: bundles.map(q => ({ id: q.id, root: q.root.question, follow: q.follow.question, source: q.sources, original: q.original })) };
    const url = URL.createObjectURL(new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' }));
    const a = document.createElement('a'); a.href = url; a.download = '콜린성-연결학습-시범결과.json'; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
    setNotice('결과와 메모의 다운로드를 요청했어요. 브라우저의 다운로드 목록에서 파일을 확인하세요.');
  }
  function reset() {
    const next = freshSession();
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(next)); setStorageBlocked(false); setWarning(''); }
    catch { setWarning('저장 공간에 접근할 수 없어 화면에서만 새로 시작합니다.'); setStorageBlocked(true); }
    setSession(next); setResetPending(false); setTab('learn'); setNotice('새 시범 학습을 시작했어요. 이전 노출이 사라진 것으로 평가하지는 않습니다.');
  }
  return <div className="shell">
    <header className="topbar"><a className="brand" href="./connection-pilot.html">Study<span>EZ</span><small>LEARNING LAB</small></a><span className="local-badge"><i/> AI 호출 없는 로컬 시범</span></header>
    <div className="intro"><div><div className="eyebrow">연결부터 배우기 / FIRST PASS</div><h1>콜린성 약리학 <span>(1)</span></h1><p>연결을 먼저 떠올리고, 설명을 붙이고, 세부로 이어갑니다.</p></div><div className="progress-box"><strong>{stats.viewed}<span> / 10 묶음</span></strong><span>첫 질문·후속 답 모두 열람</span><progress max={10} value={stats.viewed}/></div></div>
    <nav className="tabs" aria-label="시범 화면"><button aria-current={tab === 'learn' ? 'page' : undefined} onClick={() => setTab('learn')}>학습하기</button><button aria-current={tab === 'review' ? 'page' : undefined} onClick={() => { dispatch({ type: 'review' }); setTab('review'); }}>연결 지도·설계 검토 <small>답 포함</small></button><button aria-current={tab === 'results' ? 'page' : undefined} onClick={() => setTab('results')}>기록·피드백</button></nav>
    {warning && <p role="alert" className="warning">{warning}</p>}
    {notice && <p role="status" className="notice">{notice}</p>}
    {tab === 'learn' && <div className="learning-layout"><aside className="path"><h2>첫 학습 경로</h2><p>순서대로 보거나 원하는 묶음으로 이동하세요.</p><div className="path-buttons">{bundles.map((q, i) => <button key={q.id} aria-label={`${i + 1}번 묶음`} aria-current={i === session.current ? 'step' : undefined} onClick={() => navigate(i)}><span>{String(i + 1).padStart(2, '0')}</span><span>연결 {i + 1}</span><small>{session.entries[q.id].follow.revealed ? '두 답 열람' : session.entries[q.id].root.revealed ? '첫 답 열람' : '시작 전'}</small></button>)}</div><p className="path-note">초안 49문항 중 첫 경로의 10묶음입니다. 모두 열어도 강의 전체 학습 완료는 아닙니다.</p></aside>
      <main className="learning-main" key={b.id}><div className="section-line"><span>연결 {session.current + 1} / 10</span><span>첫 질문 → 설명 → 후속 질문</span></div>
        {session.reviewSeen && <p className="exposure">연결 지도·검토 화면을 열어본 기록이 있어요. 아래 결과는 독립 회상 점수가 아닌 학습 기록입니다.</p>}
        <PromptCard prompt={b.root} step={entry.root} onAction={dispatch} id={b.id} name="root"/>
        {entry.root.revealed ? <><div className="connector">이 연결에 세부를 붙여볼까요? ↓</div><PromptCard prompt={b.follow} step={entry.follow} onAction={dispatch} id={b.id} name="follow"/></> : <div className="locked">후속 질문은 첫 답을 확인한 뒤 나타나요. 미리 답의 단서가 보이지 않도록 했어요.</div>}
        {entry.follow.revealed && <section className="connection-summary"><div className="eyebrow">이번에 연결한 것</div><p>{b.connection}</p><p className="muted">다음: {b.next}</p><details><summary>질문 역할·중요도 근거·남은 질문</summary><Evidence b={b}/></details></section>}
        <section className="feedback"><label htmlFor="feedback">이 묶음에 대한 메모</label><textarea id="feedback" value={entry.feedback} maxLength={5000} onChange={e => dispatch({ type: 'feedback', id: b.id, value: e.target.value })} placeholder="질문이 막연했나요? 답을 미리 알려줬나요? 빠진 연결이 있나요?"/></section>
        <div className="navigation"><button disabled={session.current === 0} onClick={() => navigate(session.current - 1)}>← 이전 묶음</button>{session.current < 9 ? <button className="primary" onClick={() => navigate(session.current + 1)}>다음 묶음 →</button> : <button className="primary" onClick={() => setTab('results')}>기록 모아보기 →</button>}</div>
      </main></div>}
    {tab === 'review' && <main className="review"><h2>무엇을 연결하고, 무엇이 남았을까?</h2><p className="muted">개념도·출처·중요도는 학습 순서와 반복을 정하는 근거입니다. 구조적 역할과 시험·임상 중요도는 별개로 봅니다.</p><div className="review-note">시범 설계 초안 · 의학 검수 완료 아님 · 검토 화면의 답 노출은 기록됩니다.</div>
      <div className="map">{bundles.map((q, i) => <article key={q.id}><div className="map-heading"><span>{String(i + 1).padStart(2, '0')}</span><h3>{q.title}</h3><span className="chip">{q.structure}</span></div><p className="map-connection">{q.connection}</p><div className="chips"><span>{q.type}</span><span>{q.role}</span></div><details><summary>근거와 부족한 질문</summary><Evidence b={q}/></details><button className="text-button" onClick={() => navigate(i)}>이 연결 학습하기 →</button></article>)}</div>
      <section className="remaining"><h3>첫 경로 뒤에 남은 가지와 세부</h3><p>장기별 반응·용도·위해, 개별 약물의 구조와 선택성, BBB, 중독 증상과 aging 등은 전체 초안의 후속 질문으로 남아 있습니다. 중요도가 낮다는 이유로 첫 노출 범위에서 없애지 않습니다.</p><p>원본과의 독립 대조, 8번 용도 목록의 인정 범위, 실제 학습자에게서 확인한 약점은 아직 확정되지 않았습니다.</p></section>
    </main>}
    {tab === 'results' && <main className="results"><h2>연결 학습 기록</h2><p className="muted">입력한 답은 자동 채점하지 않습니다. 항목별 표시는 자기확인이며 숙련도·시험 점수가 아닙니다.</p><div className="stat-grid">{[[stats.viewed, '두 답을 열어본 묶음'], [stats.attempted, '답을 적고 공개한 질문'], [stats.recalled, '떠올렸다고 표시한 항목'], [stats.partial + stats.learned, '일부만·새로 배운 항목']].map(([n, label]) => <div key={label}><strong>{n}</strong><span>{label}</span></div>)}</div><p>자기확인 미표시: {stats.unchecked}항목 · 지도·검토 화면: {session.reviewSeen ? '열어봄' : '열지 않음'}</p>
      <div className="result-list">{bundles.map((q, i) => { const e = session.entries[q.id]; const missing = [e.root, e.follow].flatMap(s => s.marks).filter(m => m === 'partial' || m === 'learned').length; return <article key={q.id}><div><strong>연결 {i + 1}</strong><p>{e.follow.revealed ? '두 답 열람' : e.root.revealed ? '첫 답만 열람' : '답 열람 전'} · 일부만·새로 배움 {missing}항목</p>{e.feedback && <p className="saved-feedback">{e.feedback}</p>}</div><button onClick={() => navigate(i)}>돌아보기</button></article>; })}</div>
      <div className="export-actions"><button className="primary" onClick={download}>결과·메모 내려받기</button><button onClick={() => setResetPending(true)}>이 시범 기록 새로 시작</button></div>
      {resetPending && <section className="warning" aria-label="새로 시작 확인"><p>이 시범의 답·자기확인·메모가 초기화됩니다. 필요한 결과는 먼저 내려받아 주세요.</p><div className="export-actions"><button onClick={() => setResetPending(false)}>취소</button><button onClick={reset}>확인하고 새로 시작</button></div></section>}
      <p className="muted">기록은 이 브라우저에만 저장됩니다. 운영 문제은행·복습 일정에는 반영되지 않습니다.</p>
    </main>}
    <footer>콜린성 약리학(1) · 연결 중심 학습 시범 / 분류로 방향을 잡고, 나열로 범위를 모읍니다.</footer>
  </div>;
}
createRoot(document.getElementById('root')!).render(<React.StrictMode><App/></React.StrictMode>);
