import { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { QuestionBody, AnswerBody } from '../../../web/src/bank/BankQuestion';
import type { BankQuestion, BankAnswer } from '../../../web/src/types/bank';
import '../../../web/src/styles/base.css';
import './compare.css';

type Item = BankQuestion & { answer: string; answer_units: string[]; explanation: string; correct_option_ids: string[] };
type Group = { title: string; before: Item[]; after: Item[] };
type Data = { groups: Group[]; pendingReview: boolean; medical: { reviews: { question_id: string; verdict: 'ok'|'doubt'|'wrong'; note: string; suggested_answer: string }[] }; design: { question_id: string; verdict: string; reason: string }[] };
function App() {
  const [data,setData]=useState<Data|null>(null); const [error,setError]=useState('');
  const [group,setGroup]=useState(0); const [mode,setMode]=useState<'before'|'after'>('after');
  const [index,setIndex]=useState(0); const [revealed,setRevealed]=useState(false); const [picked,setPicked]=useState(new Set<string>());
  useEffect(()=>{fetch('/comparison-data.json').then(r=>{if(!r.ok)throw Error('아직 비교 자료를 준비하고 있습니다.');return r.json();}).then(setData).catch(e=>setError(String(e.message)));},[]);
  function reset(next:number){setIndex(next);setRevealed(false);setPicked(new Set());}
  if(!data)return <main><h1>Main Quiz 문항 비교</h1><p>{error||'불러오는 중…'}</p></main>;
  const rows=data.groups[group][mode];const q=rows[index];
  if(!q)return <main><h1>Main Quiz 문항 비교</h1><p>이 범위의 새 문항은 검수 결과를 확인하고 있습니다.</p></main>;
  const review=mode==='after'?data.medical.reviews.find(r=>r.question_id===q.question_id):undefined;
  const design=mode==='after'?data.design.find(r=>r.question_id===q.question_id):undefined;
  const answer:BankAnswer={answer:q.answer,answerUnits:q.answer_units,explanation:q.explanation,
    correctOptionIds:q.correct_option_ids,answerPairs:[],correctOrder:[],slides:[],medicalReview:review??null};
  return <main>
    <header><p className="eyebrow">Main Quiz · 문항 비교</p><h1>한 번에 떠올릴 수 있는 질문으로</h1><p>세 가지 범위의 이전 문항과 새 문항을 직접 비교해 보세요.</p></header>
    {data.pendingReview?<p role="status">새 문항의 원본·설계·정답 검수를 진행하고 있습니다.</p>:null}
    <nav aria-label="문항 범위">{data.groups.map((g,i)=><button key={g.title} aria-pressed={group===i} onClick={()=>{setGroup(i);reset(0);}}>{g.title}</button>)}</nav>
    <div className="version-switch" role="group" aria-label="문항 버전">{(['before','after']as const).map(m=><button key={m} aria-pressed={mode===m} onClick={()=>{setMode(m);reset(0);}}>{m==='before'?'변경 전':'변경 후'} · {data.groups[group][m].length}문항</button>)}</div>
    <article className="quiz-card"><div className="item-meta"><span>{mode==='before'?'이전 문항':'새 문항'} {index+1} / {rows.length}</span><span>{({basic:'단답',list:'나열',cloze:'빈칸',mcq:'객관식',multi_select:'복수 선택',ox:'O/X'}as Record<string,string>)[q.format]??q.format}</span></div>
      {review&&review.verdict!=='ok'?<p role="status">정답 조건 확인 필요 · 검수 의견은 답 확인 후 볼 수 있습니다.</p>:null}
      <QuestionBody question={q} answer={revealed?answer:null} picked={picked} onPick={id=>setPicked(s=>{const n=new Set(s);if(n.has(id))n.delete(id);else n.add(id);return n;})} />
      {revealed?<section className="revealed"><AnswerBody question={q} answer={answer}/>
        {design&&design.verdict!=='ok'?<p role="alert">문항 설계 확인 필요: {design.reason}</p>:null}</section>
        :<button className="reveal" onClick={()=>setRevealed(true)}>답 확인</button>}
    </article>
    <footer><button disabled={index===0} onClick={()=>reset(index-1)}>이전 문항</button><button disabled={index===rows.length-1} onClick={()=>reset(index+1)}>다음 문항</button></footer>
    <p className="footnote">기존 Main Quiz 문항 표시를 사용하는 별도 비교 화면입니다. 기존 풀이 기록은 이어받지 않습니다.</p>
  </main>;
}
createRoot(document.getElementById('root')!).render(<App/>);
