import { useCallback, useEffect, useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import { api, ApiError } from "../api";
import { lectureHref } from "../links";
import type { BankRead, BankSession } from "../types/bank";
import { BankStart } from "./BankStart";
import { RootLearningPage } from "./RootLearning";
import { RootGenerationPanel } from "./RootGenerationPanel";
import { useMe } from "../useMe";
import { useAuth } from "../auth";
import { ConnectionEntry } from "./ConnectionLearning";
import { BankSolve } from "./BankSolve";
import { useBankUndo } from "./useBankUndo";
import { useMainQuizEntry } from './useMainQuizEntry';
import { useSolvingChrome } from '../shell/studyChrome';

/**
 * Main Quiz 공통 진입. 검토·공개·계정 범위를 통과한 새 자료를 우선한다.
 * 기존 은행과 학습 기록은 아래 호환 화면에서 기존 서버 정책 그대로 사용한다.
 */
export function BankStudyPage() {
  const { subject = "", runId = "" } = useParams();
  const { session } = useAuth();
  const [search] = useSearchParams();
  const legacy = search.get('legacy') === '1';
  const account = session?.user.id ?? '';
  const scope = JSON.stringify([account, subject, runId]);
  const {entry,error}=useMainQuizEntry(subject,runId,!legacy);
  if(legacy)return <LegacyBankStudyPage key={scope}/>;
  if(error)return <p role="alert" className="notice is-error">{error}</p>;
  if(!entry)return <p className="notice" role="status">Main-Quiz를 불러오는 중…</p>;
  return entry.mode==='structured'?<RootLearningPage/>:<LegacyBankStudyPage key={scope}/>;
}

function LegacyBankStudyPage() {
  const { subject = "", runId = "" } = useParams();
  const base = `/api/lectures/${encodeURIComponent(subject)}/${encodeURIComponent(runId)}/bank`;
  const [info, setInfo] = useState<BankRead | null>(null);
  const [error, setError] = useState("");
  const [undoError, setUndoError] = useState("");
  const [solving, setSolving] = useState(false);
  const [finished, setFinished] = useState<BankSession | null>(null);
  const [unavailable, setUnavailable] = useState(false);
  const admin = useMe()?.isAdmin;
  const restore = useCallback(() => { setFinished(null); setSolving(true); }, []);
  const { undo, undoBusy } = useBankUndo(base, info?.undoToken, restore, setUndoError, solving);
  useSolvingChrome(solving);

  const load = useCallback(() => {
    api<BankRead>(base)
      .then((answer) => {
        setInfo(answer);
        setSolving(answer.session?.status === "active");
      })
      .catch((cause) => {
        if (cause instanceof ApiError && cause.status === 404) setUnavailable(true);
        else setError((cause as Error).message);
      });
  }, [base]);
  useEffect(load, [load]);
  useEffect(() => {
    // 장시간 뒤 돌아온 시작 화면은 현재 기억 추정을 다시 읽는다. 풀이 중 문항은 유지한다.
    if (solving) return;
    window.addEventListener("focus", load);
    return () => window.removeEventListener("focus", load);
  }, [load, solving]);
  useEffect(() => { document.title = "Main-Quiz · Study_EZ"; }, []);
  const onFinished = useCallback((summary: BankSession | null) => {
    setFinished(summary);
    setSolving(false);
    setInfo(null);
    load();
  }, [load]);

  if (error) return <p className="notice is-error">{error}</p>;
  if (unavailable || (info && !info.summary.usable)) return (
    <section className="quiz bank-start">
      <h2>Main-Quiz</h2>
      <p>아직 공개된 문제가 없습니다.</p>
      <ConnectionEntry subject={subject} runId={runId}/>
      {admin&&<RootGenerationPanel subject={subject} runId={runId} onPublished={()=>window.location.reload()}/>}
      <a href={lectureHref({ subject, runId })}>강의 자료와 기존 Main-Quiz 보기</a>
    </section>
  );
  if (!info) return <p className="notice">불러오는 중…</p>;

  if (solving) {
    return (
      <BankSolve
        base={base}
        lecture={{ subject, runId }}
        onFinished={onFinished}
      />
    );
  }
  return (
    <>
    {undoError ? <p role="alert" className="notice is-error">{undoError}</p> : null}
    <BankStart
      base={base}
      info={info}
      onChanged={load}
      finished={finished}
      lecture={{ subject, runId }}
      onStarted={() => {
        setFinished(null);
        setSolving(true);
      }}
      onUndo={info.undoToken ? () => void undo() : undefined}
      undoBusy={undoBusy}
    />
    </>
  );
}
