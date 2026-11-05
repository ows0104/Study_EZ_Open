import { bundles, REVISION } from './data';

export const STORAGE_KEY = `studyez:connection-pilot:${REVISION}`;
export type Mark = '' | 'recalled' | 'partial' | 'learned';
export type Step = { response: string; revealed: boolean; marks: Mark[] };
export type Entry = { root: Step; follow: Step; feedback: string };
export type Session = { revision: string; current: number; reviewSeen: boolean; entries: Record<string, Entry> };
export type Action =
  | { type: 'select'; index: number }
  | { type: 'review' }
  | { type: 'response'; id: string; step: 'root' | 'follow'; value: string }
  | { type: 'reveal'; id: string; step: 'root' | 'follow' }
  | { type: 'mark'; id: string; step: 'root' | 'follow'; index: number; value: Mark }
  | { type: 'feedback'; id: string; value: string };
function blankStep(count: number): Step { return { response: '', revealed: false, marks: Array(count).fill('') }; }
export function freshSession(): Session {
  return { revision: REVISION, current: 0, reviewSeen: false, entries: Object.fromEntries(bundles.map(b => [b.id, {
    root: blankStep(b.root.answers.length), follow: blankStep(b.follow.answers.length), feedback: '',
  }])) };
}
export function reduceSession(state: Session, action: Action): Session {
  if (action.type === 'select') return Number.isInteger(action.index) && action.index >= 0 && action.index < bundles.length ? { ...state, current: action.index } : state;
  if (action.type === 'review') return { ...state, reviewSeen: true };
  const old = state.entries[action.id];
  if (!old) return state;
  if (action.type === 'feedback') return { ...state, entries: { ...state.entries, [action.id]: { ...old, feedback: action.value.slice(0, 5000) } } };
  if (action.step === 'follow' && !old.root.revealed) return state;
  const step = old[action.step];
  let updated = step;
  if (action.type === 'response' && !step.revealed) updated = { ...step, response: action.value.slice(0, 10000) };
  if (action.type === 'reveal') updated = { ...step, revealed: true };
  if (action.type === 'mark' && step.revealed && Number.isInteger(action.index) && action.index >= 0 && action.index < step.marks.length && ['', 'recalled', 'partial', 'learned'].includes(action.value)) {
    updated = { ...step, marks: step.marks.map((m, i) => i === action.index ? action.value : m) };
  }
  return { ...state, entries: { ...state.entries, [action.id]: { ...old, [action.step]: updated } } };
}
export function decodeSession(raw: string): Session {
  const parsed: unknown = JSON.parse(raw);
  if (!parsed || typeof parsed !== 'object') throw new Error('저장 형식 오류');
  const p = parsed as Session;
  if (p.revision !== REVISION || typeof p.reviewSeen !== 'boolean' || !Number.isInteger(p.current) || p.current < 0 || p.current >= bundles.length || !p.entries) throw new Error('저장 판 또는 위치 오류');
  const clean = freshSession();
  clean.current = p.current; clean.reviewSeen = p.reviewSeen;
  for (const b of bundles) {
    const entry = p.entries[b.id];
    if (!entry || typeof entry.feedback !== 'string') throw new Error('저장 항목 오류');
    for (const key of ['root', 'follow'] as const) {
      const step = entry[key];
      if (!step || typeof step.response !== 'string' || typeof step.revealed !== 'boolean' || !Array.isArray(step.marks) || step.marks.length !== b[key].answers.length || !step.marks.every(m => ['', 'recalled', 'partial', 'learned'].includes(m)) || (!step.revealed && step.marks.some(Boolean))) throw new Error('저장 단계 오류');
      clean.entries[b.id][key] = { response: step.response.slice(0, 10000), revealed: step.revealed, marks: [...step.marks] };
    }
    if (!entry.root.revealed && (entry.follow.revealed || entry.follow.response)) throw new Error('단계 순서 오류');
    clean.entries[b.id].feedback = entry.feedback.slice(0, 5000);
  }
  return clean;
}
export function summarize(state: Session) {
  const entries = Object.values(state.entries);
  const steps = entries.flatMap(e => [e.root, e.follow]);
  const marks = steps.flatMap(s => s.marks);
  return {
    viewed: entries.filter(e => e.root.revealed && e.follow.revealed).length,
    attempted: steps.filter(s => s.revealed && s.response.trim()).length,
    recalled: marks.filter(m => m === 'recalled').length,
    partial: marks.filter(m => m === 'partial').length,
    learned: marks.filter(m => m === 'learned').length,
    unchecked: marks.filter(m => !m).length,
  };
}
