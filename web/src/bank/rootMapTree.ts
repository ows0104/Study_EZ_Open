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

export const SIZE={root:{w:210,h:64},concept:{w:260,h:66},target:{w:330,h:64}} as const;
const GAP_X=72,GAP_Y=12,GROUP_Y=22;

export type Placed = {id:string;x:number;y:number;w:number;h:number};
/** Left-to-right tidy tree of the expanded part. x,y = top-left corner. */
export function layout(tree:Tree,expanded:Set<string>){
  const placed=new Map<string,Placed>();
  const depthOf=new Map<string,number>();
  const visibleKids=(id:string)=>id===tree.rootId||expanded.has(id)?tree.nodes.get(id)!.children:[];
  (function depth(id:string,d:number){depthOf.set(id,d);visibleKids(id).forEach(c=>depth(c,d+1));})(tree.rootId,0);
  const colWidth:number[]=[];
  for(const [id,d] of depthOf)colWidth[d]=Math.max(colWidth[d]??0,SIZE[tree.nodes.get(id)!.kind].w);
  const colX=colWidth.map((_,i)=>colWidth.slice(0,i).reduce((s,w)=>s+w+GAP_X,0));
  let cursor=0;
  function place(id:string):{top:number;bottom:number}{
    const n=tree.nodes.get(id)!,size=SIZE[n.kind],x=colX[depthOf.get(id)!];
    const kids=visibleKids(id);
    if(!kids.length){const y=cursor;cursor+=size.h+GAP_Y;placed.set(id,{id,x,y,w:size.w,h:size.h});return {top:y,bottom:y+size.h};}
    const spans=kids.map((c,i)=>{if(i>0&&tree.nodes.get(c)!.kind==='concept'&&visibleKids(c).length)cursor+=GROUP_Y-GAP_Y;return place(c);});
    const top=spans[0].top,bottom=spans[spans.length-1].bottom;
    // Centre on the first and last child centres, never above the cursor that placed them.
    const centre=(top+bottom)/2,y=Math.max(centre-size.h/2,0);
    placed.set(id,{id,x,y,w:size.w,h:size.h});
    if(kids.length&&id!==tree.rootId&&tree.nodes.get(kids[kids.length-1])!.kind==='concept')cursor+=GROUP_Y-GAP_Y;
    return {top:Math.min(top,y),bottom:Math.max(bottom,y+size.h)};
  }
  place(tree.rootId);
  let width=0,height=0;
  for(const p of placed.values()){width=Math.max(width,p.x+p.w);height=Math.max(height,p.y+p.h);}
  const edges=[...placed.values()].filter(p=>p.id!==tree.rootId).map(p=>({from:tree.nodes.get(p.id)!.parent!,to:p.id}));
  return {placed,edges,width,height};
}
