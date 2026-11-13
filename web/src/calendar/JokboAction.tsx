import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, ApiError } from "../api";
import { jokboHref } from "../links";
import type { JokboSummary } from "../types/jokbo";

/**
 * 강의 패널의 「족보」 칸(2026-11-13 사용자 지시).
 *
 * **시간표 칸에 붙는다.** 올해 필기가 아직 없어 강의(Lecture)가 없는 칸에서도 족보는 있다.
 * 족보가 없는 칸(404)에서는 칸 자체를 그리지 않는다.
 */
export function JokboAction({ eventId }: { eventId: string }) {
  const [summary, setSummary] = useState<JokboSummary | null>(null);

  useEffect(() => {
    let alive = true;
    setSummary(null);
    api<JokboSummary>(`/api/jokbo/events/${encodeURIComponent(eventId)}/summary`)
      .then(got => { if (alive) setSummary(got); })
      .catch((cause: unknown) => {
        // 없음(404)은 조용히 — 족보가 없는 칸이 대부분이다.
        if (!(cause instanceof ApiError && cause.status === 404)) console.warn("jokbo summary", cause);
      });
    return () => { alive = false; };
  }, [eventId]);

  if (!summary) return null;
  const other = summary.otherItems + summary.unknownItems;
  return (
    <section className="panel-group is-jokbo">
      <h3 className="panel-group-head">
        <span>족보</span>
        {summary.audience === "admin" ? <em className="jokbo-admin-tag">관리자만</em> : null}
      </h3>
      <Link className="action-button is-quiz is-jokbo" to={jokboHref(eventId)}>
        ▶ 족보 퀴즈<b>{summary.items}</b>
      </Link>
      <p className="jokbo-split">
        <span>같은 교수 <b>{summary.sameItems}</b></span>
        <span>다른 교수 <b>{other}</b></span>
      </p>
    </section>
  );
}
