import { useEffect, useRef, useState, type CSSProperties } from 'react';
import { ROOT_TIERS } from '../types/rootLearning';
import type { RootTierName } from '../types/rootLearning';

/** 고른 중요도를 슬라이더 구간으로: 가장 낮은 것~가장 높은 것(옛 비연속 선택도). 비면 전부. */
export function tierSpan(tiers:readonly RootTierName[]):[number,number] {
  const picked=tiers.map(t=>ROOT_TIERS.indexOf(t)).filter(i=>i>=0);
  return picked.length?[Math.min(...picked),Math.max(...picked)+1]:[0,ROOT_TIERS.length];
}

/**
 * 중요도 범위 슬라이더(2026-11-25-lecture-tier-range). 선분 4개(중요도마다 하나, 이름·수는 선분 위)와 경계 점 5개.
 * 손잡이 둘이 점 위에 있고 그 사이 선분들이 고른 중요도다. 손잡이는 겹치지 않아 늘 한 선분 이상이다.
 * 선분 이름을 누르면 가까운 손잡이가 와서 그 선분을 넣는다.
 * live가 아니면 끄는 동안은 화면만, 놓을 때(pointerup·키·blur) 달라졌으면 한 번 onChange(저장하는 곳).
 * live면 움직일 때마다 onChange(모아풀기 시작 화면, 2026-11-27-mix-lane-focus — 저장하지 않는다).
 * label: 한 화면에 여럿일 때 손잡이 이름 앞에 붙인다.
 */
export function TierRange({tiers,counts,disabled,onChange,live=false,label=''}:{tiers:readonly RootTierName[];
  counts:Partial<Record<RootTierName,number>>;disabled:boolean;onChange:(tiers:RootTierName[])=>void;live?:boolean;label?:string}) {
  const end=ROOT_TIERS.length;
  const [from,to]=tierSpan(tiers);
  const [draft,setDraft]=useState<[number,number]>([from,to]);
  const draftRef=useRef(draft);
  const set=(next:[number,number])=>{draftRef.current=next;setDraft(next);};
  // 밖의 값(저장 응답·다른 강의로 이동·전체 슬라이더)이 바뀌면 손잡이도 따라간다.
  useEffect(()=>{set([from,to]);},[from,to]);
  const commit=(next=draftRef.current)=>{
    const chosen=ROOT_TIERS.slice(next[0],next[1]);
    if(chosen.join()!==tiers.join())onChange(chosen);
  };
  const [lo,hi]=draft;
  const move=(next:[number,number])=>{set(next);if(live)commit(next);};
  const pick=(i:number)=>{
    const next:[number,number]=i<lo?[i,hi]:i>=hi?[lo,i+1]:i-lo<=hi-1-i?[i,hi]:[lo,i+1];
    set(next);commit(next);
  };
  const prefix=label?label+' ':'';
  const thumb=(which:0|1)=><input type="range" min={0} max={end} step={1} value={draft[which]} disabled={disabled}
    aria-label={prefix+(which?'중요도 끝':'중요도 시작')}
    aria-valuetext={which?`${ROOT_TIERS[draft[1]-1]}까지`:`${ROOT_TIERS[draft[0]]}부터`}
    onChange={e=>{const v=Number(e.currentTarget.value);move(which?[lo,Math.max(lo+1,v)]:[Math.min(hi-1,v),hi]);}}
    onPointerUp={()=>commit()} onKeyUp={()=>commit()} onBlur={()=>commit()}/>;
  return <div className="mq-range" style={{'--lo':lo/end,'--hi':hi/end} as CSSProperties}>
    <div className="mq-range-stops">
      {ROOT_TIERS.map((tier,i)=><button key={tier} type="button" disabled={disabled}
        className={[i>=lo&&i<hi?'is-in':'',counts[tier]?'':'is-empty'].filter(Boolean).join(' ')||undefined}
        onClick={()=>pick(i)}>{tier}<b>{(counts[tier]??0).toLocaleString('ko-KR')}</b></button>)}
    </div>
    <div className="mq-range-track" aria-hidden="true"><i/>
      {Array.from({length:end+1},(_,i)=><span key={i} className={i>=lo&&i<=hi?'is-in':undefined} style={{left:`${i/end*100}%`}}/>)}
    </div>
    {thumb(0)}{thumb(1)}
  </div>;
}
