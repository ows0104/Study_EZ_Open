import { useSyncExternalStore } from 'react';
import type { Entry } from './data';

/**
 * 강의록 회독(자가 기록). 프로토타입에서는 localStorage에만 둔다.
 * 값은 「기본값에서 더하고 뺀 수」라서 가짜 데이터가 바뀌어도 기록이 엉키지 않는다.
 */
const KEY = 'proto-note-reads';
const listeners = new Set<() => void>();
let delta: Record<string, number> = (() => {
  try {
    return JSON.parse(localStorage.getItem(KEY) ?? '{}') as Record<string, number>;
  } catch {
    return {};
  }
})();

function subscribe(fn: () => void) {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

export function useNoteReads() {
  const snapshot = useSyncExternalStore(subscribe, () => delta);
  const count = (e: Entry) => Math.max(0, e.noteReads + (snapshot[e.id] ?? 0));
  const change = (e: Entry, by: 1 | -1) => {
    const next = Math.max(0, e.noteReads + (delta[e.id] ?? 0) + by);
    delta = { ...delta, [e.id]: next - e.noteReads };
    localStorage.setItem(KEY, JSON.stringify(delta));
    listeners.forEach((fn) => fn());
  };
  return { count, change };
}
