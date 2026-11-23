import { lazy, Suspense, useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { api } from '../api';
import { bankHref, lectureHref } from '../links';
import type { BankTier } from '../types/bank';
import type { RootListPage, RootListRow, RootQuestionDetail, RootQuestionList } from '../types/rootLearning';
import { AnswerBody, QuestionBody } from './BankQuestion';
import { PersonalQuestionDialog, type PersonalQuestionResult } from './PersonalQuestionDialog';
import './catalog.css';
import './question-list.css';

/**
 * Main-Quiz 강의 문항 전체 보기(docs/changes/2026-11-23-lecture-question-list).
 * 한 강의의 문항·답·형식·중요도·참고 쪽을 한 화면에. 참고 슬라이드는 쪽 번호만 두고 누를 때 불러온다.
 * 열람은 아무것도 기록하지 않는다. 수정·제보와 내 중요도는 풀이 화면과 같은 API(내 계정만).
 */
const PdfSlides = lazy(() => import('./RootPdfSlides').then(m => ({default:m.RootPdfSlides})));
const JokboSlides = lazy(() => import('./RootPdfSlides').then(m => ({default:m.RootJokboSlides})));

const FORMATS: Record<string,string> = {basic:'단답', cloze:'빈칸', list:'나열', ox:'O/X', mcq:'객관식', multi_select:'복수 선택',
  matching:'짝짓기', sequence:'순서'};
const TIERS: Record<BankTier,string> = {Essential:'★ Must-Know', Core:'Core', Important:'Important', Optional:'Optional'};
const TIER_ORDER = Object.keys(TIERS) as BankTier[];
const normalize = (text:string) => text.toLocaleLowerCase().replace(/\s+/g,'');
const endpoint = (subject:string,runId:string) => `/api/root-learning/lectures/${encodeURIComponent(subject)}/${encodeURIComponent(runId)}`;

export function RootQuestionListPage() {
  const {subject='',runId=''} = useParams();
  return <QuestionList key={`${subject}/${runId}`} subject={subject} runId={runId}/>;
}

function QuestionList({subject,runId}:{subject:string;runId:string}) {
  const base = endpoint(subject,runId);
  const [list,setList] = useState<RootQuestionList|null>(null);
  const [error,setError] = useState('');
  const [revision,setRevision] = useState(0);
  const [search,setSearch] = useState('');
  const [format,setFormat] = useState('all');
  const [tier,setTier] = useState('all');
  const [mineOnly,setMineOnly] = useState(false);
  const [hideAnswers,setHideAnswers] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    setError('');
    void api<RootQuestionList>(base+'/questions',{signal:controller.signal})
      .then(value => {if(!controller.signal.aborted)setList(value);})
      .catch(cause => {if(!controller.signal.aborted)setError((cause as Error).message);});
    return () => controller.abort();
  },[base,revision]);
  useEffect(() => {document.title = `${list?.title?`${list.title} · `:''}전체 문항 · Study_EZ`;},[list?.title]);
  const labels = useMemo(() => new Map(list?.sources.map(s => [s.sourceId,s.label])),[list]);
  const formats = useMemo(() => [...new Set(list?.questions.map(r => r.question.format))],[list]);
  const rows = useMemo(() => {
    const needle = normalize(search);
    return (list?.questions ?? []).map((row,index) => ({row,number:index+1})).filter(({row}) => {
      const q = row.question;
      if(format!=='all'&&q.format!==format)return false;
      // 「Core 이상」 = Essential·Core. TIER_ORDER는 높은 중요도부터다.
      if(tier!=='all'&&TIER_ORDER.indexOf(q.tier)>TIER_ORDER.indexOf(tier as BankTier))return false;
      if(mineOnly&&!q.personalEdited&&!q.personalTier)return false;
      return !needle||normalize(`${q.question_id} ${q.question} ${row.answer.answer} ${row.answer.explanation??''}`).includes(needle);
    });
  },[list,search,format,tier,mineOnly]);
  // 수정·중요도 저장 뒤 그 행만 바꾼다. 목록 전체를 다시 받지 않는다.
  function replace(id:string,change:(row:RootListRow)=>RootListRow) {
    setList(current => current&&{...current,questions:current.questions.map(r => r.question.question_id===id?change(r):r)});
  }
  const filtered = search||format!=='all'||tier!=='all'||mineOnly;
  return <section className="bank-catalog root-question-list">
    <header className="catalog-heading">
      <div><p>{subject}{list?.title?` · ${list.title}`:''}</p><h1>전체 문항</h1>
        <p>Main-Quiz 문항을 한 번에 봅니다. 열람해도 학습 기록과 복습 일정은 바뀌지 않습니다.
          수정·내 중요도는 내 계정에만 적용됩니다.</p></div>
      <div className="catalog-links">
        <Link to={lectureHref({subject,runId})}>강의 자료</Link>
        <Link to={bankHref({subject,runId})}>Main-Quiz로 →</Link></div>
    </header>
    {error?<div role="alert" className="notice is-error">{error} <button onClick={() => setRevision(v => v+1)}>다시 불러오기</button></div>
      :!list?<p className="notice" role="status">전체 문항을 불러오는 중…</p>:<>
        <div className="catalog-toolbar">
          <label>검색 <input type="search" value={search} onChange={e => setSearch(e.target.value)} placeholder="발문 · 정답 · 해설 · 문항 ID"/></label>
          <label>형식 <select value={format} onChange={e => setFormat(e.target.value)}>
            <option value="all">전체</option>{formats.map(f => <option key={f} value={f}>{FORMATS[f]??f}</option>)}</select></label>
          <label>중요도 <select value={tier} onChange={e => setTier(e.target.value)}>
            <option value="all">전체</option>{TIER_ORDER.slice(0,-1).map(t => <option key={t} value={t}>{TIERS[t]} 이상</option>)}</select></label>
          <label><input type="checkbox" checked={mineOnly} onChange={e => setMineOnly(e.target.checked)}/>내가 고친 문항만</label>
          <label><input type="checkbox" checked={hideAnswers} onChange={e => setHideAnswers(e.target.checked)}/>정답 가리기</label>
          <span role="status">{rows.length} / {list.questions.length}문항</span>
        </div>
        <div className="catalog-cards">
          {rows.map(({row,number}) => <QuestionCard key={`${list.revision}:${row.question.question_id}`} row={row} number={number}
            base={base} editable={list.editable} labels={labels} hideAnswer={hideAnswers}
            onChange={change => replace(row.question.question_id,change)}/>)}
        </div>
        {!rows.length&&<div className="catalog-empty"><p>{list.questions.length?'조건에 맞는 문항이 없습니다.':'등록된 문항이 없습니다.'}</p>
          {filtered&&<button onClick={() => {setSearch('');setFormat('all');setTier('all');setMineOnly(false);}}>모든 문항 보기</button>}</div>}
      </>}
  </section>;
}

function QuestionCard({row,number,base,editable,labels,hideAnswer,onChange}:{row:RootListRow;number:number;base:string;editable:boolean;
  labels:Map<string,string>;hideAnswer:boolean;onChange:(change:(row:RootListRow)=>RootListRow)=>void}) {
  const q = row.question, qid = q.question_id;
  const [detail,setDetail] = useState<RootQuestionDetail|null>(null);
  const [loading,setLoading] = useState(false);
  const [error,setError] = useState('');
  const [page,setPage] = useState<RootListPage|null>(null);
  const [revealed,setRevealed] = useState(false);
  const [editing,setEditing] = useState(false);
  const [tierBusy,setTierBusy] = useState(false);
  const [note,setNote] = useState('');
  async function load() {
    if(detail||loading)return;
    setLoading(true);setError('');
    try{setDetail(await api<RootQuestionDetail>(`${base}/questions/${encodeURIComponent(qid)}/detail`));}
    catch(cause){setError((cause as Error).message);}
    finally{setLoading(false);}
  }
  function openPage(next:RootListPage) {
    setPage(current => current&&current.sourceId===next.sourceId&&current.page===next.page?null:next);
    void load();
  }
  async function changeTier(value:BankTier) {
    setTierBusy(true);setNote('');
    try{
      const got = await api<{question:RootListRow['question']}>(`${base}/questions/${encodeURIComponent(qid)}/tier`,
        {method:'PUT',body:JSON.stringify({requestId:crypto.randomUUID(),tier:value})});
      onChange(r => ({...r,question:{...r.question,tier:got.question.tier,personalTier:got.question.personalTier,originalTier:got.question.originalTier}}));
      if(detail)setDetail({...detail,question:{...detail.question,tier:got.question.tier,personalTier:got.question.personalTier}});
      setNote(got.question.personalTier?`내 중요도를 ${TIERS[got.question.tier]}로 저장했습니다.`:'원래 중요도로 되돌렸습니다.');
    }catch(cause){setError((cause as Error).message);}
    finally{setTierBusy(false);}
  }
  function saved(result:PersonalQuestionResult,reset:boolean) {
    setEditing(false);
    onChange(r => ({...r,question:{...result.question,figures:r.question.figures},answer:result.answer}));
    setDetail(current => current&&{...current,question:result.question,answer:{...result.answer,memo:current.answer.memo}});
    setNote(reset?'원본으로 되돌렸습니다.':(result.highlighted?'강조 제보를 보냈습니다.':'관리자에게 전달했습니다.')+(result.question.personalEdited?' 내 수정본을 저장했습니다.':''));
  }
  const shown = detail?.question ?? q;
  const answer = detail?.answer ?? row.answer;
  const answerOpen = !hideAnswer||revealed;
  const slide = page&&detail?(page.exam?detail.answer.jokboPdfSlides:detail.answer.pdfSlides)?.find(s => s.sourceId===page.sourceId&&s.page===page.page):undefined;
  const groups = groupPages(row.pages);
  return <article className="catalog-card rq-card" aria-label={`${number}번 문항`}>
    <header>
      <span className="catalog-number">{String(number).padStart(2,'0')}</span>
      <span className="rq-format">{FORMATS[q.format]??q.format}</span>
      <label className={`rq-tier${q.tier==='Essential'?' catalog-essential':''}`} title="내 계정의 이 문제에만 적용됩니다. 중요도가 목표 기억률을 정합니다.">
        <span className="sr-only">내 중요도</span>
        <select value={q.tier} disabled={tierBusy} onChange={e => void changeTier(e.target.value as BankTier)} aria-label={`${number}번 문항 내 중요도`}>
          {TIER_ORDER.map(t => <option key={t} value={t}>{TIERS[t]}</option>)}</select></label>
      {q.personalTier&&<span className="tag">내 중요도{q.originalTier?` · 원래 ${TIERS[q.originalTier]}`:''}</span>}
      {q.personalEdited&&<span className="tag">내 수정본</span>}
      {!row.planned&&<span className="tag" title="이 문항은 오늘 학습 계획에 들어가지 않습니다(준비 전·연결 확인 필요 등).">학습 과제 없음</span>}
      <small>{qid}</small>
      <button type="button" className="is-quiet rq-edit" onClick={() => setEditing(true)}>{editable?'수정·제보':'제보'}</button>
    </header>
    <QuestionBody question={shown} answer={answerOpen?answer:null} picked={new Set()} onPick={() => {}} disabled showChoiceScore={false}/>
    {q.figures>0&&!detail?.question.stimuli?.length&&<button type="button" className="is-quiet rq-figures" disabled={loading} onClick={() => void load()}>
      {loading?'그림 불러오는 중…':`그림 ${q.figures}개 불러오기`}</button>}
    {answerOpen?<div className="catalog-answer rq-answer"><AnswerBody question={shown} answer={answer} reviewInline={false}/></div>
      :<button type="button" className="catalog-reveal" onClick={() => setRevealed(true)}>정답·해설 보기 ↓</button>}
    <div className="rq-pages" aria-label="참고 쪽">
      <span>참고 쪽</span>
      {groups.length?groups.map(({sourceId,exam,pages}) => <span key={sourceId} className="rq-source">
        <b title={labels.get(sourceId)}>{exam?'족보':'강의록'}{groups.filter(g => g.exam===exam).length>1?` · ${labels.get(sourceId)??sourceId}`:''}</b>
        {pages.map(p => <button key={p.page} type="button" className="rq-page" aria-pressed={page?.sourceId===p.sourceId&&page.page===p.page}
          onClick={() => openPage(p)}>{p.page}</button>)}</span>):<span className="bank-note">연결된 쪽 없음</span>}
    </div>
    {page&&<div className="rq-slide">
      {loading?<p role="status">슬라이드를 불러오는 중…</p>:error?<p role="alert" className="notice is-error">{error}
        <button onClick={() => {setError('');void load();}}>다시 시도</button></p>
      :slide?<Suspense fallback={<p role="status">슬라이드를 준비하고 있습니다…</p>}>
        {page.exam?<JokboSlides slides={[slide]}/>:<PdfSlides slides={[slide]}/>}</Suspense>
      :detail&&<p className="bank-note">이 쪽의 슬라이드를 불러올 수 없습니다(원본이 PDF가 아니거나 판 원본과 다릅니다).
        {detail.answer.sourceLinks?.map((s,i) => <a key={i} href={s.url} target="_blank" rel="noreferrer"> {s.label}</a>)}</p>}
    </div>}
    {!page&&error&&<p role="alert" className="notice is-error">{error}</p>}
    {note&&<p className="bank-note" role="status">{note}</p>}
    {editing&&<PersonalQuestionDialog path={`${base}/questions/${encodeURIComponent(qid)}/personal`} questionId={qid}
      answerVisible onClose={() => setEditing(false)} onSaved={saved}/>}
  </article>;
}

/** 원본별로 쪽을 묶는다(강의록 먼저, 쪽 순). */
function groupPages(pages:RootListPage[]) {
  const groups = new Map<string,{sourceId:string;exam:boolean;pages:RootListPage[]}>();
  for(const p of pages){
    const g = groups.get(p.sourceId) ?? {sourceId:p.sourceId,exam:p.exam,pages:[]};
    g.pages.push(p);groups.set(p.sourceId,g);
  }
  return [...groups.values()].map(g => ({...g,pages:[...g.pages].sort((a,b) => a.page-b.page)}))
    .sort((a,b) => Number(a.exam)-Number(b.exam));
}

