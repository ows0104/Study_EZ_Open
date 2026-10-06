// 실제 캘린더 칸으로 달 모양과 관리자·학생의 같은 풀이 비율을 확인한다.
import { useState } from "react";
import { createRoot } from "react-dom/client";
import { EventChip, ChipSlots } from "../src/calendar/EventChip";
import type { CalendarEntry } from "../src/calendar/entries";
import type { LectureRef } from "../src/types/lectures";
import "../src/styles/base.css";
import "../src/styles/calendar.css";

function Harness() {
  const [admin, setAdmin] = useState(false);
  return <main style={{maxWidth: 800, margin: "24px auto", padding: 24}}>
    <h1>캘린더 예습 진행</h1>
    <p>도전 포함 6문항 · 덱을 받은 경우에도 웹 풀이 비율을 표시합니다.</p>
    <label><input type="checkbox" checked={admin} onChange={e=>setAdmin(e.target.checked)} /> 관리자 계정</label>
    <div style={{display:"grid", gridTemplateColumns:"repeat(auto-fit, minmax(150px, 1fr))", gap:20, marginTop:24}}>
      {[0,1,2,3,4,5,6].map(answered=>{
        const lecture: LectureRef = {subject:"약리학",runId:`261006_0${answered+1}`,title:"약동학",professors:[],
          marks:{notesPrev:true,preview:true,prequiz:true,notesCurrent:true,quiz:true},
          grabbed:{pre:true,main:false},prequizProgress:{answered,total:6}};
        const entry: CalendarEntry = {id:String(answered),title:`${answered}/6문항 완료`,date:"2026-10-06",
          startTime:"09:00",endTime:"10:00",detail:"",professor:"담당 교수",category:"lecture",course:"약리학",lectures:[lecture]};
        return <div key={answered}>
          <div style={{height:88}}><EventChip entry={entry} compact={false} active={false} isAdmin={admin} onOpen={()=>{}} /></div>
          <div style={{position:"relative",height:55,marginTop:14}}>
            <span style={{position:"absolute",left:"50%",top:20,transform:"scale(4)"}}><ChipSlots lecture={lecture} isAdmin={admin} /></span>
          </div>
        </div>;
      })}
    </div>
  </main>;
}
createRoot(document.getElementById("root")!).render(<Harness />);
