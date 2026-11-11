import { useCallback, useEffect, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
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
 * Main Quiz 공통 진입. 검토·공개·계정 범위를 통과한 Main-Quiz만 연다(2026-11-11부터 Quiz Bank는 legacy).
 * 옛 Quiz Bank 문제와 기록은 `?legacy=1`로만 연다. 기록은 기존 서버 정책 그대로 보존한다.
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
  return entry.mode==='structured'?<RootLearningPage/>:<NoMainQuiz subject={subject} runId={runId}/>;
}

function NoMainQuiz({ subject, runId }: { subject: string; runId: string }) {
  return (
    <section className="quiz bank-start">
      <p className="notice">이 강의의 Main-Quiz가 아직 열리지 않았습니다.</p>
      <p className="bank-note"><Link to={lectureHref({ subject, runId })}>강의로 돌아가기</Link>
        {" · "}<Link to={`/bank/${encodeURIComponent(subject)}/${encodeURIComponent(runId)}?legacy=1`}>옛 Quiz Bank 기록 보기</Link></p>
    </section>
  );
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
    <p className="notice">옛 Quiz Bank 기록입니다. 사이트 학습률·시험 계획에는 포함되지 않습니다.</p>
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
