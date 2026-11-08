import type { RootMapData, RootSummary } from '../types/rootLearning';

/*
 * Concept map as a tree: lecture → concepts → questions (targets).
 *
 * Only real data is used. A concept's explicit parent_ids nest concepts; a target hangs
 * under its anchor concept — the one of its concepts shared by the most targets (the
 * topic, e.g. C001), not the answer node made for that single question (N1_A). Same-label
 * siblings are one node (the published 감염병리1 판 has C001/C002 with the same title).
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

  let leaves=0,currentId:string|null=null;
  for(const t of map.targets){
    const anchor=[...t.concept_ids].filter(id=>concepts.has(id)).sort((a,b)=>(uses.get(b)??0)-(uses.get(a)??0))[0];
    const parent=anchor?placeConcept(anchor):(nodes.get('c:__other')?.id??(()=>{
      const n=add({id:'c:__other',kind:'concept',label:'기타',parent:ROOT_ID,conceptIds:[]});nodes.get(ROOT_ID)!.children.push(n.id);return n.id;})());
    const pages=[...new Set((t.evidence??[]).flatMap(e=>e.pages??[]).filter(p=>Number.isInteger(p)&&p>0))].sort((a,b)=>a-b);
    const status=targetStatus(t.target_id,t.directions.some(d=>ready.has(d.direction_id)),summary);
    const current=t===currentTarget;
    const leaf=add({id:'t:'+t.target_id,kind:'target',label:plain(t.title),parent,conceptIds:t.concept_ids,targetId:t.target_id,pages,status,current});
    nodes.get(parent)!.children.push(leaf.id);leaves++;
    if(current)currentId=leaf.id;
  }

  // Aggregate pages/status upward, then order children by first page (lecture order).
  const first=(n:TreeNode)=>n.pages[0]??Number.MAX_SAFE_INTEGER;
  (function walk(id:string){
    const n=nodes.get(id)!;
    for(const c of n.children){walk(c);const child=nodes.get(c)!;
      n.pages=[...new Set([...n.pages,...child.pages])].sort((a,b)=>a-b);
      if(child.kind==='target')n.counts[child.status!]++;else for(const k of Object.keys(n.counts) as Status[])n.counts[k]+=child.counts[k];
      if(child.current)n.current=true;}
    const order=new Map(n.children.map((c,i)=>[c,i]));
    n.children.sort((a,b)=>first(nodes.get(a)!)-first(nodes.get(b)!)||order.get(a)!-order.get(b)!);
  })(ROOT_ID);
  // Concepts that anchor nothing (answer nodes, unused labels) are not tree nodes.
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
