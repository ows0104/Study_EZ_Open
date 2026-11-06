import { useCallback, useState } from "react";
import { Link } from "react-router-dom";
import { bumpPreviewVersion } from "../bridge/previewBridge";
import { ActionCard, PanelGroup } from "../calendar/panelShared";
import { bankCatalogHref, bankHref } from "../links";
import type { BankSummary } from "../types/bank";
import type { LectureDetail, LectureRef } from "../types/lectures";
import { useMe } from "../useMe";
import { RootGenerationPanel } from './RootGenerationPanel';
import { useMainQuizEntry } from './useMainQuizEntry';

/** 웹 문항 생성 → CLI 검수·보완 → Main-Quiz 게시·학습. */
export function BankPanel({ lecture, detail }: { lecture: Pick<LectureRef, "subject" | "runId">; detail: LectureDetail }) {
  const isAdmin = Boolean(useMe()?.isAdmin);
  const bank = detail.bank;
  const [version,setVersion]=useState(0);
  const {entry,error}=useMainQuizEntry(lecture.subject,lecture.runId,true,version);
  const published=useCallback(()=>{setVersion(v=>v+1);bumpPreviewVersion();},[]);
  const summary=entry?.mode==='structured'?entry.overview.summary:null;
  return (
    <>
      <PanelGroup tone="main" title="Main Quiz" note="개념과 학습 목표에 맞춰 복습">
        {error?<p role="alert" className="panel-hint">{error}</p>:!entry?<p className="panel-hint">학습 자료 확인 중…</p>:
          entry.mode==='structured'?<ActionCard shape="is-key" hit={<Link className="panel-action-hit" to={bankHref(lecture)}>
            <strong>공부하기</strong><small>{summary?`목표 첫 학습 ${summary.learned}/${summary.total} · 회상 가능 ${summary.recalled}`:'검토된 학습 자료 준비됨'}</small>
          </Link>}/>:bank?.usable?<StudyCard lecture={lecture} bank={bank}/>:<p className="panel-hint">아직 공개된 문제가 없습니다.</p>}
        {isAdmin&&<RootGenerationPanel subject={lecture.subject} runId={lecture.runId} onPublished={published}/>}
      </PanelGroup>
      {isAdmin&&bank?.respondedAt&&<p className="panel-hint"><Link to={`/admin/bank-cards/${encodeURIComponent(lecture.subject)}/${encodeURIComponent(lecture.runId)}`}>기존 문항 검토·수정 →</Link></p>}
    </>
  );
}

function StudyCard({ lecture, bank, tools }: {
  lecture: Pick<LectureRef, "subject" | "runId">;
  bank: BankSummary;
  tools?: React.ReactNode;
}) {
  return (
    <>
      <ActionCard
        shape="is-key"
        hit={
          <Link className="panel-action-hit" to={bankHref(lecture)}>
            <strong>공부하기</strong>
            <small>{bank.seenQuestionCount}/{bank.studyQuestionCount}문항 봄 · 개념 {bank.conceptCount}개</small>
          </Link>
        }
        tools={tools}
      />
      <p className="panel-hint"><Link to={bankCatalogHref(lecture)}>전체 문제 · 슬라이드 순서로 보기 →</Link></p>
    </>
  );
}
