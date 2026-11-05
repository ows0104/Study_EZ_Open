import { useCallback, useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api, ApiError } from "../api";
import { lectureHref } from "../links";
import type { BankRead, BankSession } from "../types/bank";
import { BankStart } from "./BankStart";
import { RootEntry } from "./RootLearning";
import { ConnectionEntry } from "./ConnectionLearning";
import { BankSolve } from "./BankSolve";
import { useBankUndo } from "./useBankUndo";

/**
 * Quiz Bank 풀이 창(2026-10-04).
 *
 *   학습을 시작한다(기본 개수 제한 없음) → 서버가 고른 문항 → 「답 보기」 → Again·Hard·Good·Easy → 다음
 *
 * **고르는 것도 일정도 서버다**(`server/app/study_engine/`). 개념 × 회상 방향마다 숙련도를 두고
 * 중요도·약점·시험까지 남은 날·선행 문항으로 다음 문항을 정한다. 화면은 그리기만 한다 —
 * 두 곳에서 고르면 갈라진다(Main-Quiz 가 `srs.py` 를 화면에 안 두는 것과 같은 까닭).
 *
 * 짝짓기·순서형의 정오답은 자동채점하고, 모든 형식의 학습 평가는 사용자가 직접 고른다.
 */
export function BankStudyPage() {
  const { subject = "", runId = "" } = useParams();
  const base = `/api/lectures/${encodeURIComponent(subject)}/${encodeURIComponent(runId)}/bank`;
  const [info, setInfo] = useState<BankRead | null>(null);
  const [error, setError] = useState("");
  const [undoError, setUndoError] = useState("");
  const [solving, setSolving] = useState(false);
  const [finished, setFinished] = useState<BankSession | null>(null);
  const [unavailable, setUnavailable] = useState(false);
  const restore = useCallback(() => { setFinished(null); setSolving(true); }, []);
  const { undo, undoBusy } = useBankUndo(base, info?.undoToken, restore, setUndoError, solving);

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
      <RootEntry subject={subject} runId={runId}/>
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
