import { useCallback, useEffect, useRef, useState } from 'react';
import type { BankFormat } from '../types/bank';

/**
 * 복습 퀴즈(Main-Quiz 풀이) 문항 타이머(2026-11-11 사용자 지시).
 * 문제: 기본 30초 · ox 20초 · matching/sequence 40초. item_difficulty는 쓰지 않는다.
 * 해설: 일괄 40초. 0초 동작(답 보기 / Again 평가)은 부르는 쪽이 정한다.
 */
export const ANSWER_SECONDS = 40;

export function questionSeconds(format: BankFormat): number {
  if (format === 'ox') return 20;
  if (format === 'matching' || format === 'sequence') return 40;
  return 30;
}

const KEY = 'studyez:quiz-timer';

/** 처음 상태는 켜짐. 저장소를 못 읽어도 켜짐으로 동작한다. */
export function readTimerOn(): boolean {
  try { return localStorage.getItem(KEY) !== 'off'; } catch { return true; }
}

export function saveTimerOn(on: boolean) {
  try { localStorage.setItem(KEY, on ? 'on' : 'off'); } catch { /* 이번 화면에서는 고른 대로 동작한다. */ }
}

/**
 * `phase`(문항·단계)가 바뀌거나 타이머를 다시 켜면 처음부터 센다.
 * 꺼짐·일시정지·`running=false`·브라우저 탭 숨김 동안에는 흐르지 않는다.
 * 0초에 `onExpire`를 단계마다 한 번만 부른다.
 */
export function useQuizTimer({ phase, seconds, enabled, running, onExpire }: {
  phase: string | null; seconds: number; enabled: boolean; running: boolean; onExpire: () => void;
}) {
  const [paused, setPaused] = useState(false);
  const [hidden, setHidden] = useState(() => typeof document !== 'undefined' && document.hidden);
  const [leftMs, setLeftMs] = useState(seconds * 1000);
  const used = useRef(0);
  const fired = useRef<string | null>(null);
  const expire = useRef(onExpire);
  expire.current = onExpire;

  useEffect(() => {
    const update = () => setHidden(document.hidden);
    document.addEventListener('visibilitychange', update);
    return () => document.removeEventListener('visibilitychange', update);
  }, []);

  useEffect(() => {
    used.current = 0; fired.current = null;
    setPaused(false); setLeftMs(seconds * 1000);
  }, [phase, enabled, seconds]);

  const flowing = !!phase && enabled && running && !paused && !hidden;
  useEffect(() => {
    if (!flowing) return;
    const from = Date.now() - used.current;
    const tick = () => {
      used.current = Date.now() - from;
      const rest = seconds * 1000 - used.current;
      setLeftMs(Math.max(0, rest));
      if (rest <= 0 && fired.current !== phase) { fired.current = phase; expire.current(); }
    };
    const id = window.setInterval(tick, 200);
    return () => { window.clearInterval(id); used.current = Date.now() - from; };
  }, [flowing, phase, seconds]);

  const togglePause = useCallback(() => setPaused(p => !p), []);
  return { left: Math.ceil(leftMs / 1000), paused, togglePause };
}
