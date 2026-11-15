import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import type { LectureRef } from "../types/lectures";

/** 패널에서 회독 수가 바뀌었다. 캘린더 칸이 듣고 회독 줄을 바로 고친다. */
export const NOTE_READS_EVENT = "studyez:note-reads";
export type NoteReadsChange = { subject: string; runId: string; count: number };

/** 줄에 그리는 강의록 토막 상한. 그 이상은 숫자로만 남는다(서버 상한 30). */
const MAX_SEGMENTS = 12;

/**
 * 통계의 회독 줄(2026-11 개편 2단계). 첫 토막 = 예습 퀴즈(끝냈을 때만), 뒤 = 강의록 회독, 그 뒤 = 족보 회독, 끝에 +.
 * 강의록 토막을 누르면 최근 1회독을 지우고 4초 동안 「되돌리기」가 뜬다.
 * 족보 토막(2026-11-14)은 족보 퀴즈 끝 화면에 닿을 때 자동으로 생기고, 여기서는 지우지 않는다.
 */
export function ReadEditor({ lecture, base, preOpen, preDone, initial, jokboRounds = 0, onError }: {
  lecture: Pick<LectureRef, "subject" | "runId">;
  base: string;
  preOpen: boolean;
  preDone: boolean;
  initial: number;
  jokboRounds?: number;
  onError: (message: string) => void;
}) {
  const [count, setCount] = useState(initial);
  const [undo, setUndo] = useState(false);
  const [busy, setBusy] = useState(false);
  const timer = useRef<number | undefined>(undefined);

  useEffect(() => setCount(initial), [initial, lecture.subject, lecture.runId]);
  useEffect(() => () => window.clearTimeout(timer.current), []);

  async function change(method: "POST" | "DELETE") {
    if (busy) return;
    setBusy(true);
    try {
      const path = method === "POST" ? `${base}/note-reads` : `${base}/note-reads/last`;
      const { noteReads } = await api<{ noteReads: number }>(path, { method });
      setCount(noteReads);
      window.dispatchEvent(new CustomEvent<NoteReadsChange>(NOTE_READS_EVENT, {
        detail: { subject: lecture.subject, runId: lecture.runId, count: noteReads },
      }));
      return true;
    } catch (cause) {
      onError((cause as Error).message);
      return false;
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    if (!(await change("DELETE"))) return;
    setUndo(true);
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => setUndo(false), 4000);
  }

  const shown = Math.min(count, MAX_SEGMENTS);
  const jokbo = Math.min(jokboRounds, MAX_SEGMENTS);
  return (
    <span className="read-editor">
      <span className="readline is-lg">
        {preDone ? <i className="rl-pre is-on" title="예습 퀴즈 완료" /> : null}
        {Array.from({ length: shown }, (_, index) => (
          <button key={index} type="button" className="rl-note is-button" title="지우기"
            aria-label={`강의록 회독 ${index + 1} 지우기`} disabled={busy} onClick={() => void remove()} />
        ))}
        {Array.from({ length: jokbo }, (_, index) => (
          <i key={`j${index}`} className="rl-jokbo" title={`족보 ${index + 1}회독`} />
        ))}
        {!preDone && !count && !jokbo && preOpen ? <i className="rl-pre" title="예습 퀴즈 미완료" /> : null}
      </span>
      {count > MAX_SEGMENTS || jokboRounds > MAX_SEGMENTS ? <span className="read-count">{count + jokboRounds}</span> : null}
      <button type="button" className="read-plus" aria-label="강의록 회독 추가" title="회독 추가"
        disabled={busy} onClick={() => { setUndo(false); void change("POST"); }}>+</button>
      {undo ? (
        <button type="button" className="read-undo" disabled={busy}
          onClick={() => { setUndo(false); void change("POST"); }}>되돌리기</button>
      ) : null}
    </span>
  );
}

const MAX_MEMO = 300;

/** 강의별 2~3줄 메모. 입력을 멈추면(0.8초) 또는 칸을 떠나면 저장한다. */
export function LectureMemo({ base, initial, onError }: { base: string; initial: string; onError: (message: string) => void }) {
  const [text, setText] = useState(initial);
  const saved = useRef(initial);
  const timer = useRef<number | undefined>(undefined);

  useEffect(() => { setText(initial); saved.current = initial; }, [initial, base]);

  async function save(value: string) {
    window.clearTimeout(timer.current);
    if (value.trimEnd() === saved.current) return;
    try {
      const { memo } = await api<{ memo: string }>(`${base}/my-memo`, { method: "PUT", body: JSON.stringify({ memo: value }) });
      saved.current = memo;
    } catch (cause) {
      onError((cause as Error).message);
    }
  }

  // 패널을 닫거나 강의를 바꾸기 직전 입력도 잃지 않는다.
  const latest = useRef(text);
  latest.current = text;
  useEffect(() => () => {
    window.clearTimeout(timer.current);
    if (latest.current.trimEnd() !== saved.current) void save(latest.current);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [base]);

  return (
    <span className="lecture-memo">
      <textarea rows={3} maxLength={MAX_MEMO} value={text} aria-label="메모"
        onChange={(event) => {
          const value = event.target.value;
          setText(value);
          window.clearTimeout(timer.current);
          timer.current = window.setTimeout(() => void save(value), 800);
        }}
        onBlur={() => void save(text)} />
    </span>
  );
}
