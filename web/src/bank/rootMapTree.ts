import type { RootMapData, RootSummary } from '../types/rootLearning';

/*
 * Concept map as a tree: lecture → concepts → questions (targets).
 *
 * Only real data is used. The tree is the 판's concept hierarchy (first explicit parent_id),
 * not something rebuilt from the questions: every concept in that hierarchy is a topic, even
 * one with no question of its own (2026-11-09 — 감염병리1 lost 항산염색 AFB and 12 others
 * when only question anchors were shown). Answer nodes (one per question: the Map 판's F…,
 * the older 판's N1_A) are not topics. A question hangs under its answer node's parent; when
 * the answer node has no parent, under its concept shared by the most questions (e.g. C001).
 * Same-label siblings are one node (the older 감염병리1 판 has C001/C002 with the same title).
 * No medical hierarchy is guessed from text.
 */
export type Status = 'is-new'|'is-learning'|'is-recalled'|'is-unready';
export const STATUS_LABEL:Record<Status,string>={'is-new':'미학습','is-learning':'학습 중','is-recalled':'회상 가능','is-unready':'준비 전'};
export type TreeNode = {id:string; kind:'root'|'concept'|'target'; label:string; parent:string|null; children:string[];
  conceptIds:string[]; targetId?:string; pages:number[]; status?:Status; current:boolean; counts:Record<Status,number>};
export type Tree = {nodes:Map<string,TreeNode>; rootId:string; currentId:string|null; leaves:number};

export const ROOT_ID='root';
/** Display text only: authored emphasis markers (**x**) are not shown as asterisks. */
export const plain=(text:string)=>text.replace(/\*\*(.+?)\*\*/g,'$1');
const empty=():Record<Status,number>=>({'is-new':0,'is-learning':0,'is-recalled':0,'is-unready':0});

export function targetStatus(targetId:string,ready:boolean,summary:RootSummary):Status{
  const s=summary.targets.find(t=>t.id===targetId);
  if(!ready||!s||!s.ready)return 'is-unready';
  if(s.recalled)return 'is-recalled';
  if(s.learned)return 'is-learning';
  return 'is-new';
}

export function buildTree(map:RootMapData,summary:RootSummary,title:string):Tree{
  const concepts=new Map(map.concepts.map(c=>[c.concept_id,c]));
  const uses=new Map<string,number>();
  for(const t of map.targets)for(const id of t.concept_ids)uses.set(id,(uses.get(id)??0)+1);
  const usedBy=new Map<string,RootMapData['targets'][number][]>();
  for(const t of map.targets)for(const id of t.concept_ids)usedBy.set(id,[...(usedBy.get(id)??[]),t]);
  const parents=new Set(map.concepts.flatMap(c=>c.parent_ids));
  const links=new Map<string,Set<string>>(),sources=new Set(map.relations.map(r=>r.from_id));
  for(const r of map.relations){
    links.set(r.from_id,(links.get(r.from_id)??new Set()).add(r.to_id));
    links.set(r.to_id,(links.get(r.to_id)??new Set()).add(r.from_id));
  }
  const parentsOf=(id:string)=>(concepts.get(id)?.parent_ids??[]).filter(p=>concepts.has(p)&&p!==id);
  /** One question's answer node: used by that question only, no children, only ever the `to` end of
   *  its links, and linked only to its parent (or, without a parent, to that question's other
   *  concepts). Real topics fail this — they are a link's `from` end or link across questions. */
  const answerNode=new Map<string,boolean>();
  function isAnswer(id:string){
    const known=answerNode.get(id);if(known!==undefined)return known;
    const ts=usedBy.get(id)??[],linked=links.get(id);
    let answer=false;
    if(ts.length===1&&!parents.has(id)&&!sources.has(id)&&linked?.size){
      const up=parentsOf(id),pool=new Set(up.length?up:ts[0].concept_ids.filter(x=>x!==id));
      answer=[...linked].every(x=>pool.has(x));
    }
    answerNode.set(id,answer);return answer;
  }
  const ready=new Set(map.readyDirectionIds??map.targets.flatMap(t=>t.directions.map(d=>d.direction_id)));
  const currentSet=new Set(map.currentConceptIds??[]);
  const currentTarget=currentSet.size?map.targets.find(t=>t.concept_ids.length===currentSet.size&&t.concept_ids.every(id=>currentSet.has(id)))
    ??map.targets.find(t=>t.concept_ids.some(id=>currentSet.has(id))):undefined;

  const nodes=new Map<string,TreeNode>();
  const add=(n:Omit<TreeNode,'children'|'counts'|'pages'|'current'>&Partial<TreeNode>)=>{
    const node:TreeNode={children:[],counts:empty(),pages:[],current:false,...n};nodes.set(node.id,node);return node;};
  add({id:ROOT_ID,kind:'root',label:title,parent:null,conceptIds:[]});

  // Concept chain (first explicit parent, cycle-safe), merged by label among siblings.
  const conceptNode=new Map<string,string>();
  function placeConcept(id:string,path:Set<string>=new Set()):string{
    const known=conceptNode.get(id);if(known)return known;
    const concept=concepts.get(id);
    const parentId=concept?.parent_ids.find(p=>concepts.has(p)&&!path.has(p)&&p!==id);
    const parent=parentId&&path.size<12?placeConcept(parentId,new Set([...path,id])):ROOT_ID;
    const label=concept?.label??id;
    const sibling=nodes.get(parent)!.children.map(c=>nodes.get(c)!).find(n=>n.kind==='concept'&&n.label===label);
    if(sibling){sibling.conceptIds.push(id);conceptNode.set(id,sibling.id);return sibling.id;}
    const node=add({id:'c:'+id,kind:'concept',label,parent,conceptIds:[id]});
    nodes.get(parent)!.children.push(node.id);conceptNode.set(id,node.id);return node.id;
  }

  // Page numbers shown are the lecture's: the source most questions cite (S1 필기), never mixed with
  // another source's pages (족보 p.1 is not lecture p.1).
  const cited=new Map<string,number>();
  for(const t of map.targets)for(const e of t.evidence??[])cited.set(e.source_id,(cited.get(e.source_id)??0)+1);
  const lecture=[...cited].sort((a,b)=>b[1]-a[1]||a[0].localeCompare(b[0]))[0]?.[0];

  let leaves=0,currentId:string|null=null;
  for(const t of map.targets){
    const own=t.concept_ids.filter(id=>concepts.has(id));
    const answerParent=own.filter(isAnswer).flatMap(parentsOf).find(p=>!isAnswer(p));
    const anchor=answerParent??own.filter(id=>!isAnswer(id)).sort((a,b)=>(uses.get(b)??0)-(uses.get(a)??0))[0];
    const parent=anchor?placeConcept(anchor):(nodes.get('c:__other')?.id??(()=>{
      const n=add({id:'c:__other',kind:'concept',label:'기타',parent:ROOT_ID,conceptIds:[]});nodes.get(ROOT_ID)!.children.push(n.id);return n.id;})());
    const pages=[...new Set((t.evidence??[]).filter(e=>e.source_id===lecture).flatMap(e=>e.pages??[]).filter(p=>Number.isInteger(p)&&p>0))].sort((a,b)=>a-b);
    const status=targetStatus(t.target_id,t.directions.some(d=>ready.has(d.direction_id)),summary);
    const current=t===currentTarget;
    const leaf=add({id:'t:'+t.target_id,kind:'target',label:plain(t.title),parent,conceptIds:t.concept_ids,targetId:t.target_id,pages,status,current});
    nodes.get(parent)!.children.push(leaf.id);leaves++;
    if(current)currentId=leaf.id;
  }

  // The rest of the hierarchy: topics without a question of their own still belong to the map.
  // Isolated labels (no parent, no child, no question, no link) stay out.
  for(const c of map.concepts){
    const id=c.concept_id;
    if(conceptNode.has(id)||isAnswer(id))continue;
    if(parentsOf(id).length||parents.has(id)||links.get(id)?.size)placeConcept(id);
  }

  // Aggregate pages/status upward. Order is the 판's own: concepts in the order the Map stage wrote
  // them while reading the lecture (C001 → …), questions in target order. Pages are not used for
  // order — one question citing an intro page pulled a whole branch forward (2026-11-09).
  const conceptAt=new Map(map.concepts.map((c,i)=>[c.concept_id,i]));
  const targetAt=new Map(map.targets.map((t,i)=>[t.target_id,i]));
  const rank=(n:TreeNode)=>n.kind==='target'?targetAt.get(n.targetId!)??0
    :map.targets.length+Math.min(...n.conceptIds.map(id=>conceptAt.get(id)??Number.MAX_SAFE_INTEGER));
  (function walk(id:string){
    const n=nodes.get(id)!;
    for(const c of n.children){walk(c);const child=nodes.get(c)!;
      n.pages=[...new Set([...n.pages,...child.pages])].sort((a,b)=>a-b);
      if(child.kind==='target')n.counts[child.status!]++;else for(const k of Object.keys(n.counts) as Status[])n.counts[k]+=child.counts[k];
      if(child.current)n.current=true;}
    n.children.sort((a,b)=>rank(nodes.get(a)!)-rank(nodes.get(b)!));
  })(ROOT_ID);
  return {nodes,rootId:ROOT_ID,currentId,leaves};
}

export function ancestors(tree:Tree,id:string){
  const out:string[]=[];let n=tree.nodes.get(id);
  while(n?.parent){out.push(n.parent);n=tree.nodes.get(n.parent);}
  return out;
}

export type LaneRow = {id:string; depth:number};
export type Lane = {head:string; rows:LaneRow[]};
/** Top-down lane view: each top-level topic is one column (lane); the topics below it follow
 *  depth-first in lecture order, with their depth under the lane head. Questions are not rows —
 *  they belong to the topic they hang under (see `questionsOf`). Nothing is collapsed. */
export function lanes(tree:Tree):Lane[]{
  const isConcept=(id:string)=>tree.nodes.get(id)!.kind==='concept';
  return tree.nodes.get(tree.rootId)!.children.filter(isConcept).map(head=>{
    const rows:LaneRow[]=[];
    (function walk(id:string,depth:number){
      for(const c of tree.nodes.get(id)!.children)if(isConcept(c)){rows.push({id:c,depth});walk(c,depth+1);}
    })(head,1);
    return {head,rows};
  });
}
export const questionsOf=(tree:Tree,id:string)=>tree.nodes.get(id)!.children.filter(c=>tree.nodes.get(c)!.kind==='target');
/** Lanes per row: everything on one row up to 8 lanes, then balanced rows so a flat map
 *  (many topics, no nesting) still keeps a screen-like shape instead of one very wide strip. */
export function lanesPerRow(count:number){
  if(count<=8)return Math.max(1,count);
  return Math.ceil(count/Math.ceil(count/8));
}
