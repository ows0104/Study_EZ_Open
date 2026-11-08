import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { api } from '../api';
import { SlidePreloader } from '../slidePreload';
import type { RootFrame, RootPdfSlide } from '../types/rootLearning';

const AHEAD = 3;
const BATCH = 4;

/**
 * Read-only look-ahead of a session's fixed task list (GET …/prepare records nothing).
 * Frames are what Space and a rating draw at once; the event is confirmed behind them.
 * Images and the first reference slide of each frame are fetched and drawn while the
 * learner is still thinking about the current question.
 */
export function useRootFrames(sessionId: string | undefined) {
  const frames = useRef(new Map<number, RootFrame>());
  const inflight = useRef(new Set<number>());
  const live = useRef(sessionId);
  const images = useMemo(() => new SlidePreloader(), []);
  const [, changed] = useState(0);
  useEffect(() => {
    live.current = sessionId;
    frames.current = new Map();
    inflight.current = new Set();
  }, [sessionId]);
  const ensure = useCallback((position: number, count: number) => {
    const sid = sessionId;
    if (!sid) return;
    let start = -1;
    for (let p = position; p < Math.min(position + AHEAD, count); p++) {
      if (!frames.current.has(p)) { start = p; break; }
    }
    if (start < 0 || [...inflight.current].some(p => p <= start && start < p + BATCH)) return;
    inflight.current.add(start);
    api<{ sessionId: string; frames: RootFrame[] }>(`/api/root-learning/sessions/${encodeURIComponent(sid)}/prepare?start=${start}&count=${BATCH}`)
      .then(result => {
        if (live.current !== sid) return;
        for (const frame of result.frames) frames.current.set(frame.position, frame);
        warm(result.frames, images);
        changed(value => value + 1);
      })
      .catch(() => {}) // A miss falls back to confirming the event, then reading the session.
      .finally(() => inflight.current.delete(start));
  }, [sessionId, images]);
  const get = useCallback((position: number) => frames.current.get(position), []);
  /** 개인 수정 뒤: 미리 받은 문항·답이 옛 문면이다. 다음 ensure가 새로 받는다. */
  const forget = useCallback(() => { frames.current = new Map(); inflight.current = new Set(); }, []);
  return { get, ensure, forget };
}

function warm(frames: RootFrame[], images: SlidePreloader) {
  const urls: string[] = [];
  const pdf: RootPdfSlide[] = [];
  for (const frame of frames) {
    if (!frame.task) continue;
    urls.push(...(frame.task.question.stimuli ?? []).map(s => s.url));
    urls.push(...frame.task.answer.slides.filter(s => s.primary).map(s => s.url));
    if (frame.task.answer.pdfSlides?.length) pdf.push(frame.task.answer.pdfSlides[0]);
  }
  images.warm(urls);
  if (pdf.length) void import('./RootPdfSlides').then(m => m.prewarmPdfSlides(pdf)).catch(() => {});
}
