import { useCallback, useEffect, useRef, useState } from 'react';
import { api } from '../api';
import { Icon } from '../shell/icons';
import type { Note, NoteInput, NoteSummary } from '../types/notes';
import { NoteEditor, formatUpdated, mk, type EditNote } from './NoteEditor';
import './notes.css';

/**
 * 자유 노트(`/notes`). 왼쪽 목록, 오른쪽 편집기. 노트는 계정별로 서버(`/api/me/notes`)에 둔다.
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
  blocks: n.blocks.map(({ id, type, html, checked }) => (type === 'todo' ? { id, type, html, checked: !!checked } : { id, type, html })),
});

type SaveState = 'idle' | 'failed';

export function NotesPage() {
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
        if (r.notes[0]) setActiveId(r.notes[0].id);
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

  const update = (fn: (n: EditNote) => EditNote) => {
    setActive((a) => {
      if (!a) return a;
      const next = fn(a);
      pending.current.set(next.id, next);
      return next;
    });
    schedule();
  };

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

  const create = async () => {
    if (busy) return;
    setBusy(true);
    try {
      await flush();
      const note = await api<Note>('/api/me/notes', { method: 'POST', body: JSON.stringify({ title: '', tags: [], blocks: [] }) });
      setList((ls) => [{ id: note.id, title: note.title, tags: note.tags, updatedAt: note.updatedAt }, ...(ls ?? [])]);
      setActive(toEdit(note));
      setActiveId(note.id);
    } catch (e) {
      setLoadError((e as Error).message);
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
    const rest = (list ?? []).filter((s) => s.id !== n.id);
    setList(rest);
    if (n.id === activeId) setActiveId(rest[0]?.id ?? '');
  };

  return (
    <div className="notes-layout">
      <aside className="notes-list" aria-label="노트 목록">
        <div className="notes-list-head">
          <strong>자유 노트</strong>
          <button className="icon-button" onClick={() => void create()} disabled={busy} title="새 노트" aria-label="새 노트"><Icon.plus /></button>
        </div>
        {list?.map((n) => (
          <div key={n.id} className={`notes-item${n.id === activeId ? ' is-active' : ''}`}>
            <button className="notes-item-open" onClick={() => void select(n.id)}>
              <span className="notes-item-icon"><Icon.file /></span>
              <span className="notes-item-text">
                <b className={n.title ? '' : 'is-empty'}>{n.title || '제목 없음'}</b>
                <small>{formatUpdated(n.updatedAt)}</small>
              </span>
            </button>
            <button className="notes-item-delete" title="삭제" aria-label={`${n.title || '제목 없음'} 삭제`} onClick={() => void remove(n)}><Icon.x /></button>
          </div>
        ))}
        <p className="notes-hint">
          <kbd>/</kbd> 블록 고르기 · <kbd>#</kbd> <kbd>-</kbd> <kbd>[]</kbd> <kbd>&gt;</kbd> 줄머리 md · <kbd>**굵게**</kbd> <kbd>`코드`</kbd> · 글을 고르면 색·하이라이트
        </p>
      </aside>
      <div className="notes-main">
        {loadError ? <p className="notes-status is-bad" role="alert">{loadError}</p> : null}
        {saveState === 'failed' ? (
          <p className="notes-status is-bad" role="alert">
            저장 실패 · <button onClick={() => void flush()}>다시 시도</button>
          </p>
        ) : null}
        {active ? (
          <NoteEditor key={active.id} note={active} update={update} />
        ) : list && !list.length ? (
          <div className="notes-empty">
            <button className="notes-new" onClick={() => void create()} disabled={busy}><Icon.plus /> 새 노트</button>
          </div>
        ) : null}
      </div>
    </div>
  );
}
