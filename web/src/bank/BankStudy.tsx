import { useCallback, useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "../api";
import type { BankRead, BankSession } from "../types/bank";
import { BankStart } from "./BankStart";
import { BankSolve } from "./BankSolve";

/**
 * Quiz Bank 풀이 창(2026-10-04).
 *
 *   회차를 연다(10·20·25·30문항) → 서버가 고른 문항 → 「답 보기」 → Again·Hard·Good·Easy → 다음
 *
 * **고르는 것도 일정도 서버다**(`server/app/study_engine/`). 개념 × 회상 방향마다 숙련도를 두고
 * 중요도·약점·시험까지 남은 날·선행 문항으로 다음 문항을 정한다. 화면은 그리기만 한다 —
 * 두 곳에서 고르면 갈라진다(Main-Quiz 가 `srs.py` 를 화면에 안 두는 것과 같은 까닭).
 *
 * 채점은 스스로 한다(자유회상). 객관식은 골라 볼 수 있지만 그것도 채점이 아니라 회상을 돕는 것이다.
 */
export function BankStudyPage() {
  const { subject = "", runId = "" } = useParams();
  const base = `/api/lectures/${encodeURIComponent(subject)}/${encodeURIComponent(runId)}/bank`;
  const [info, setInfo] = useState<BankRead | null>(null);
  const [error, setError] = useState("");
  const [solving, setSolving] = useState(false);
  const [finished, setFinished] = useState<BankSession | null>(null);

  const load = useCallback(() => {
    api<BankRead>(base)
      .then((answer) => {
        setInfo(answer);
        setSolving(answer.session?.status === "active");
      })
      .catch((cause) => setError((cause as Error).message));
  }, [base]);
  useEffect(load, [load]);

  if (error) return <p className="notice is-error">{error}</p>;
  if (!info) return <p className="notice">불러오는 중…</p>;
  if (!info.summary.usable) return <p className="notice">이 강의의 Quiz Bank 는 아직 공부할 수 없습니다.</p>;

  if (solving) {
    return (
      <BankSolve
        base={base}
        onFinished={(summary) => {
          setFinished(summary);
          setSolving(false);
          load();
        }}
      />
    );
  }
  return (
    <BankStart
      base={base}
      info={info}
      finished={finished}
      lecture={{ subject, runId }}
      onStarted={() => {
        setFinished(null);
        setSolving(true);
      }}
    />
  );
}
