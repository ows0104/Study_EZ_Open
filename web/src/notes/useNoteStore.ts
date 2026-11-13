import { useCallback, useEffect, useRef, useState } from 'react';
import { api } from '../api';
import type { Note, NoteInput, NoteSummary } from '../types/notes';
import { deleteNoteImages } from './localImages';
import { mk, type EditNote } from './NoteEditor';

/**
 * 자유 노트 목록·불러오기·저장. `/notes` 화면과 플로팅 노트 창이 같이 쓴다(2026-11-13).
 * 고친 뒤 잠시 쉬면 저장하고, 다른 노트로 옮기거나 화면을 떠날 때 남은 저장을 먼저 보낸다.
 */

const SAVE_DELAY = 700;

const toEdit = (n: Note): EditNote => ({
  id: n.id,
  title: n.title,
  tags: n.tags,
  updatedAt: n.updatedAt,
  blocks: n.blocks.length ? n.blocks.map((b) => ({ ...b, rev: 0 })) : [mk('text')],
});

const toInput = (n: EditNote): NoteInput => ({
  title: n.title,
  tags: n.tags,
  blocks: n.blocks.map(({ id, type, html, checked, image }) =>
    type === 'todo' ? { id, type, html, checked: !!checked }
      : type === 'image' ? { id, type, html: '', image }
        : { id, type, html }),
});

type SaveState = 'idle' | 'failed';

export function useNoteStore({ userId, pick }: { userId: string; pick?: (notes: NoteSummary[]) => string }) {
  const [list, setList] = useState<NoteSummary[] | null>(null);
  const [loadError, setLoadError] = useState('');
  const [activeId, setActiveId] = useState('');
  const [active, setActive] = useState<EditNote | null>(null);
  const [saveState, setSaveState] = useState<SaveState>('idle');
  const [busy, setBusy] = useState(false);

  // 저장 대기: 노트 id → 최신 내용. 한 노트에 저장은 한 번에 하나만 보내고, 그사이 바뀐 내용은 이어서 보낸다.
  const pending = useRef(new Map<string, EditNote>());
  const timer = useRef<number | undefined>(undefined);
  const inflight = useRef<Promise<void> | null>(null);
  const pickRef = useRef(pick);
  pickRef.current = pick;

  const flush = useCallback(async (): Promise<void> => {
    window.clearTimeout(timer.current);
    if (inflight.current) {
      await inflight.current;
      if (pending.current.size) return flush();
      return;
    }
    const next = pending.current.entries().next();
    if (next.done) return;
    const [id, note] = next.value;
    pending.current.delete(id);
    inflight.current = (async () => {
      try {
        const saved = await api<Note>(`/api/me/notes/${id}`, { method: 'PUT', body: JSON.stringify(toInput(note)) });
        setList((ls) => ls?.map((s) => (s.id === id ? { id, title: saved.title, tags: saved.tags, updatedAt: saved.updatedAt } : s)) ?? ls);
        setActive((a) => (a && a.id === id ? { ...a, updatedAt: saved.updatedAt } : a));
        setSaveState('idle');
      } catch {
        // 실패한 내용은 다시 보낼 수 있게 남긴다(그사이 더 새 내용이 들어왔으면 그것이 이긴다).
        if (!pending.current.has(id)) pending.current.set(id, note);
        setSaveState('failed');
        throw new Error('save failed');
      } finally {
        inflight.current = null;
      }
    })();
    try {
      await inflight.current;
    } catch {
      return;
    }
    if (pending.current.size) return flush();
  }, []);

  const schedule = useCallback(() => {
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => void flush(), SAVE_DELAY);
  }, [flush]);

  // 처음 목록
  useEffect(() => {
    api<{ notes: NoteSummary[] }>('/api/me/notes')
      .then((r) => {
        setList(r.notes);
        const first = pickRef.current?.(r.notes) || r.notes[0]?.id;
        if (first) setActiveId(first);
      })
      .catch((e: Error) => setLoadError(e.message));
  }, []);

  // 고른 노트 내용
  useEffect(() => {
    if (!activeId) {
      setActive(null);
      return;
    }
    if (active?.id === activeId) return;
    let alive = true;
    setActive(null);
    api<Note>(`/api/me/notes/${activeId}`)
      .then((n) => alive && setActive(toEdit(n)))
      .catch((e: Error) => alive && setLoadError(e.message));
    return () => {
      alive = false;
    };
  }, [activeId]); // eslint-disable-line react-hooks/exhaustive-deps

  // 떠날 때 남은 저장
  useEffect(() => {
    const onHide = () => {
      if (document.visibilityState === 'hidden') void flush();
    };
    const onUnload = (ev: BeforeUnloadEvent) => {
      if (pending.current.size || inflight.current) {
        void flush();
        ev.preventDefault();
      }
    };
    document.addEventListener('visibilitychange', onHide);
    window.addEventListener('beforeunload', onUnload);
    return () => {
      document.removeEventListener('visibilitychange', onHide);
      window.removeEventListener('beforeunload', onUnload);
      void flush();
    };
  }, [flush]);

  const update = useCallback((fn: (n: EditNote) => EditNote) => {
    setActive((a) => {
      if (!a) return a;
      const next = fn(a);
      pending.current.set(next.id, next);
      return next;
    });
    schedule();
  }, [schedule]);

  // 목록의 제목·태그는 쓰는 대로 따라간다(저장 전에도).
  useEffect(() => {
    if (!active) return;
    setList((ls) => ls?.map((s) => (s.id === active.id && (s.title !== active.title || s.tags !== active.tags)
      ? { ...s, title: active.title, tags: active.tags } : s)) ?? ls);
  }, [active?.id, active?.title, active?.tags]); // eslint-disable-line react-hooks/exhaustive-deps

  const select = async (id: string) => {
    if (id === activeId) return;
    await flush();
    setActiveId(id);
  };

  /** 새 노트. 만든 노트(편집 상태)를 돌려준다. */
  const create = async (): Promise<EditNote | null> => {
    if (busy) return null;
    setBusy(true);
    try {
      await flush();
      const note = await api<Note>('/api/me/notes', { method: 'POST', body: JSON.stringify({ title: '', tags: [], blocks: [] }) });
      setList((ls) => [{ id: note.id, title: note.title, tags: note.tags, updatedAt: note.updatedAt }, ...(ls ?? [])]);
      const edit = toEdit(note);
      setActive(edit);
      setActiveId(note.id);
      return edit;
    } catch (e) {
      setLoadError((e as Error).message);
      return null;
    } finally {
      setBusy(false);
    }
  };

  const remove = async (n: NoteSummary) => {
    if (!window.confirm(`「${n.title || '제목 없음'}」 노트를 삭제할까요?`)) return;
    pending.current.delete(n.id);
    await flush();
    try {
      await api(`/api/me/notes/${n.id}`, { method: 'DELETE' });
    } catch (e) {
      setLoadError((e as Error).message);
      return;
    }
    void deleteNoteImages(n.id, userId).catch(() => {});
    const rest = (list ?? []).filter((s) => s.id !== n.id);
    setList(rest);
    if (n.id === activeId) setActiveId(rest[0]?.id ?? '');
  };

  return { list, loadError, setLoadError, activeId, active, saveState, busy, flush, update, select, create, remove };
}
