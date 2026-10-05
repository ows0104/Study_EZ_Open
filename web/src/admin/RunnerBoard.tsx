import { useState } from "react";
import { api } from "../api";
import type { JobBoard, PrequizJob } from "../types/jobs";
import { progressLine, waitingUntil } from "../jobProgress";

/**
 * 지금 무엇이 도는가. **표보다 먼저 선다.**
 *
 * 「지금 어떤 걸 하고 있고, 돌린 지 몇 분째이고, 어느 단계까지 왔고, 예상 시간은
 * 얼마인지」를 보려면 그 전에는 표를 훑어야 했다(2026-09-01 관리자 지시). 도는
 * 것도 기다리는 것도 없으면 아무것도 안 그린다.
 */
export function RunnerBoard({ board, onBoard }: { board: JobBoard | null; onBoard: (next: JobBoard) => void }) {
  // 옮기는 동안 그 줄의 버튼만 잠근다. 응답이 줄 전체를 들고 오므로
  // (`prequiz_jobs.board`) 두 번 눌러도 상하지는 않지만, 두 번째 누름은
  // 첫 번째가 만든 자리를 다시 옮긴다.
  const [moving, setMoving] = useState(0);
  const [moveError, setMoveError] = useState("");
  // **한 번 누르면 안 지운다.** 도는 편을 멈추는 것은 15분을 버리는 일이고,
  // 줄을 지우는 것은 그날 그 편이 안 만들어진다는 뜻이다. 되돌리는 길이
  // 「다시 누르기」뿐이라 묻는 값이 싸다.
  const [confirming, setConfirming] = useState(0);

  async function cancel(job: PrequizJob) {
    setMoving(job.id);
    setMoveError("");
    setConfirming(0);
    try {
      onBoard(await api<JobBoard>(`/api/admin/prequiz-jobs/${job.id}/cancel`, { method: "POST" }));
    } catch (cause) {
      setMoveError((cause as Error).message);
    } finally {
      setMoving(0);
    }
  }

  /**
   * 지우거나 멈추는 자리. **하는 일이 상태를 보고 갈린다** — 기다리는 줄은 그
   * 자리에서 끝나고, 도는 편은 러너가 받아 가야 끝난다(서버는 그 프로세스를
   * 모른다). 그래서 말도 갈라 적는다.
   */
  function cancelButton(job: PrequizJob) {
    const stopping = job.state === "running";
    const stuck = stopping && job.cancelRequested;
    const label = stuck ? "강제로 내리기" : stopping ? "멈추기" : "지우기";
    if (confirming !== job.id) {
      return (
        <button className="is-quiet" disabled={moving === job.id} onClick={() => setConfirming(job.id)}>
          {label}
        </button>
      );
    }
    return (
      <>
        {/* 무엇이 일어나는지 한 마디로. 「멈추기」와 「강제로 내리기」는 결과가
            다르다 — 뒤의 것은 노트북이 계속 만들고 있을 수 있다. */}
        <button className="is-danger" disabled={moving === job.id} onClick={() => void cancel(job)}>
          {stuck ? "줄에서 내린다" : stopping ? "정말 멈춘다" : "정말 지운다"}
        </button>
        <button className="is-quiet" onClick={() => setConfirming(0)}>
          그만
        </button>
      </>
    );
  }

  /**
   * 러너가 물어 놓은 줄에 답한다. 고른 전략을 싣고 다시 줄에 선다.
   *
   * 2026-09-24 관리자 지시 — 표시해 둔 편은 돌릴 때 알림을 띄워 고르게. 무엇을
   * 묻는지는 러너가 정하고(`runner.watch.strategy_question`) 여기는 답만 보낸다.
   */
  async function choose(job: PrequizJob, strategy: string) {
    setMoving(job.id);
    setMoveError("");
    try {
      onBoard(await api<JobBoard>(`/api/admin/prequiz-jobs/${job.id}/choose`, {
        method: "POST",
        body: JSON.stringify({ strategy }),
      }));
    } catch (cause) {
      setMoveError((cause as Error).message);
    } finally {
      setMoving(0);
    }
  }

  async function move(job: PrequizJob, to: "front" | "back") {
    setMoving(job.id);
    setMoveError("");
    try {
      // **바뀐 줄을 그대로 받는다.** 다시 읽으면 그 사이에 러너가 한 편 집어 가고,
      // 화면은 자기가 방금 옮긴 줄이 어디로 갔는지 못 말한다.
      onBoard(await api<JobBoard>(`/api/admin/prequiz-jobs/${job.id}/move`, {
        method: "POST",
        body: JSON.stringify({ to }),
      }));
    } catch (cause) {
      setMoveError((cause as Error).message);
    } finally {
      setMoving(0);
    }
  }

  if (!board) return null;
  const { running, waiting } = board;
  // 러너가 묻는 줄과 상한에 걸린 줄은 **사람이 할 일이 다르다** — 앞의 것은 골라야
  // 움직이고, 뒤의 것은 캘린더에서 누르면 풀린다. 한 무더기로 두면 앞의 것이 묻힌다.
  const asking = board.held.filter((job) => job.ask);
  const held = board.held.filter((job) => !job.ask);
  if (!running.length && !waiting.length && !board.held.length) return null;
  return (
    <section className="runner-board">
      <h2>
        지금 도는 것 {running.length}/{board.maxRunning}
        {waiting.length ? ` · 기다리는 것 ${waiting.length}` : ""}
        {asking.length ? ` · 전략을 골라야 할 것 ${asking.length}` : ""}
        {held.length ? ` · 상한에 걸린 것 ${held.length}` : ""}
        {` · 오늘 자동 ${board.autoUsedToday}/${board.autoDailyCap}편`}
      </h2>

      {/* **맨 위에 선다.** 사람이 고르기 전에는 아무것도 안 움직이는 줄이다. */}
      {asking.map((job) => (
        <div key={job.id} className="runner-job runner-ask">
          <span>
            <strong>
              {job.subject}/{job.runId}
            </strong>{" "}
            {job.kind === "main" ? "Main-Quiz" : "Pre-Quiz"} · 전략을 골라 주세요
            <br />
            <small>{job.ask}</small>
          </span>
          <span className="runner-move">
            {/* 이름은 `runner watch --strategy` 가 받는 그대로다. 「사진」은 실습용이라
                뺐다 — 표시해 두는 편이 강의이기 때문이다. */}
            {[
              ["기본", "기본"],
              ["족보", "족보 중심"],
              ["필기", "필기 중심"],
            ].map(([value, label]) => (
              <button key={value} disabled={moving === job.id} onClick={() => void choose(job, value)}>
                {label}
              </button>
            ))}
            {cancelButton(job)}
          </span>
        </div>
      ))}

      {running.map((job) => (
        <div key={job.id} className="runner-job">
          <span>
            <strong>
              {job.subject}/{job.runId}
            </strong>{" "}
            {job.kind === "main" ? "Main-Quiz" : "Pre-Quiz"}
            {job.origin === "auto" ? " · 자동" : ""}
            <small> {job.worker}</small>
            <br />
            {/* **「멈추는 중」을 「만드는 중」으로 두면 안 된다.** 러너가 받아 갈
                때까지 몇십 초가 걸리는데, 그동안 화면이 그대로면 누른 사람이
                안 눌린 줄 알고 다시 누른다(그러면 강제로 내려간다). */}
            {job.cancelRequested ? (
              <small>멈추는 중 — 러너가 이 편을 놓기를 기다린다 · {progressLine(job, false)}</small>
            ) : (
              <small>{progressLine(job)}</small>
            )}
            {/* 시간으로 그린다. 단계 수로 그리면 「② 카드」 하나가 편의 절반이라
                막대가 절반에서 오래 멈춰 선다. 남은 시간을 모르면 안 그린다. */}
            {job.etaSeconds > 0 ? (
              <span className="runner-bar">
                <span
                  style={{
                    width: `${Math.min(99, Math.round((job.elapsedSeconds / (job.elapsedSeconds + job.etaSeconds)) * 100))}%`,
                  }}
                />
              </span>
            ) : null}
          </span>
          <span className="runner-move">{cancelButton(job)}</span>
        </div>
      ))}

      {/* **왜 이 순서인가**를 줄 위에 한 번 적는다. 줄마다 「내일 예습」이 붙어
          있어도, 그것이 순위라는 것은 규칙을 봐야 안다. */}
      {waiting.length > 1 ? (
        <p className="runner-rule">순서: 내일 예습 → 오늘 복습 → 선 순서대로. 옮기면 그 위에 선다.</p>
      ) : null}

      {waiting.map((job, index) => (
        <div key={job.id} className="runner-job">
          <span>
            <strong>
              {job.subject}/{job.runId}
            </strong>{" "}
            {job.kind === "main" ? "Main-Quiz" : "Pre-Quiz"}
            {/* 한도로 멈춘 줄은 차례를 기다리는 것이 아니라 **시각**을 기다린다.
                그 자리에 「차례 1번째」만 적으면 곧 시작할 것으로 읽힌다. */}
            {waitingUntil(job) ? (
              <small> · 세션 한도 — {waitingUntil(job)}에 저절로 이어 감</small>
            ) : (
              <small>
                {" "}
                · 차례 {index + 1}번째
                {/* 순위는 **서버가 붙여 보낸다**. 여기서 날짜를 다시 세면 하루가
                    바뀌는 시각이 두 자리에서 갈린다(서버는 새벽 5시로 센다). */}
                {job.priority ? ` · ${job.priority}` : ""}
                {job.queueRank !== 0 ? " · 손으로 옮김" : ""}
                {job.origin === "auto" ? " · 자동" : ""}
              </small>
            )}
          </span>
          <span className="runner-move">
            {/* 줄이 하나뿐이면 옮길 데가 없다. 그때 버튼을 그려 두면 누를 수 있는
                것처럼 보이고, 눌러도 아무 일이 안 난다. **지우기는 그때도 뜬다** —
                한 줄짜리 큐에서도 그 한 줄을 안 만들 수 있다. */}
            {waiting.length > 1 && confirming !== job.id ? (
              <>
                <button
                  className="is-quiet"
                  disabled={moving === job.id || index === 0}
                  onClick={() => move(job, "front")}
                >
                  맨 앞으로
                </button>
                <button
                  className="is-quiet"
                  disabled={moving === job.id || index === waiting.length - 1}
                  onClick={() => move(job, "back")}
                >
                  맨 뒤로
                </button>
              </>
            ) : null}
            {cancelButton(job)}
          </span>
        </div>
      ))}
      {moveError ? <p className="notice is-error">{moveError}</p> : null}

      {held.map((job) => (
        <div key={job.id} className="runner-job">
          <span>
            <strong>
              {job.subject}/{job.runId}
            </strong>{" "}
            {job.kind === "main" ? "Main-Quiz" : "Pre-Quiz"}
            <br />
            {/* 상한에 걸린 줄은 **왜 안 만드는지**를 그대로 적는다. 만드는 버튼은
                캘린더의 그 덱 칸이다 — 여기서 또 누르게 하면 같은 버튼이 둘이 된다.
                지우는 자리는 반대다. 큐를 보는 곳이 여기뿐이라 여기 있어야 한다. */}
            <small>{job.stage || "오늘 자동 상한을 넘어 기다리는 중"}</small>
          </span>
          <span className="runner-move">{cancelButton(job)}</span>
        </div>
      ))}
    </section>
  );
}
