import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api';
import { Icon } from '../shell/icons';
import type { LectureDetail } from '../types/lectures';
import { NoteEditor, type NoteEditorHandle } from './NoteEditor';
import { useNoteStore } from './useNoteStore';
import './notes.css';

/**
 * 플로팅 노트 창(2026-11-13). 열 때마다 서버에서 새로 읽고(`/notes`에서 고친 내용을 덮지 않게), 닫을 때 남은 저장을 보낸다.
 * 창 안의 키 입력은 바깥 퀴즈 단축키(숫자·V·Z·Space…)로 새지 않게 막는다 — 퀴즈 처리기는 window에서 듣는다.
 */

const LAST = 'studyez.floatingNote';
const QUIZ_PATH = /^\/(?:prequiz|mainquiz|legacy-mainquiz|bank)\/([^/]+)\/([^/]+)/;

function readLast() {
  try {
    return localStorage.getItem(LAST) ?? '';
  } catch {
    return '';
  }
}

/** 화면이 알린 강의명. 없으면 퀴즈 주소의 강의에서 읽는다. */
function useLectureTitle(announced: string | null, pathname: string) {
  const [fetched, setFetched] = useState<{ path: string; title: string } | null>(null);
  const m = announced ? null : pathname.match(QUIZ_PATH);
  const key = m ? `${m[1]}/${m[2]}` : '';
  useEffect(() => {
    if (!key) return;
    let alive = true;
    const [subject, runId] = key.split('/');
    api<LectureDetail>(`/api/lectures/${subject}/${runId}`)
      .then((d) => alive && setFetched({ path: key, title: d.title }))
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, [key]);
  return announced || (fetched && fetched.path === key ? fetched.title : null);
}

export default function FloatingNotePanel({ userId, lecture, pathname, onClose }: {
  userId: string;
  lecture: string | null;
  pathname: string;
  onClose: () => void;
}) {
  const { list, loadError, activeId, active, saveState, busy, flush, update, select, create } = useNoteStore({
    userId,
    pick: (notes) => {
      const last = readLast();
      return notes.some((n) => n.id === last) ? last : '';
    },
  });
  const handle = useRef<NoteEditorHandle | null>(null);
  const pendingInsert = useRef<string | null>(null);
  const title = useLectureTitle(lecture, pathname);

  useEffect(() => {
    if (!activeId) return;
    try {
      localStorage.setItem(LAST, activeId);
    } catch {
      /* 저장 못 해도 다음에 최근 노트를 연다 */
    }
  }, [activeId]);

  // 노트가 없을 때 누른 「＋강의명」: 새 노트가 그려진 뒤 넣는다.
  useEffect(() => {
    if (active && pendingInsert.current && handle.current) {
      handle.current.insertText(pendingInsert.current);
      pendingInsert.current = null;
    }
  });

  const insertLecture = () => {
    if (!title) return;
    if (active && handle.current) handle.current.insertText(title);
    else if (list && !list.length) {
      pendingInsert.current = title;
      void create();
    }
  };

  const stop = (ev: { nativeEvent: Event }) => ev.nativeEvent.stopPropagation();

  return (
    <section className="notes-layout note-float" role="dialog" aria-label="자유 노트" onKeyDown={stop} onKeyUp={stop} onKeyPress={stop}>
      <header className="note-float-head">
        <select
          className="note-float-pick"
          aria-label="노트 고르기"
          value={activeId}
          disabled={!list?.length}
          onChange={(ev) => void select(ev.target.value)}
        >
          {list?.map((n) => <option key={n.id} value={n.id}>{n.title || '제목 없음'}</option>)}
        </select>
        <button type="button" className="note-float-icon" onClick={() => void create()} disabled={busy} title="새 노트" aria-label="새 노트"><Icon.plus /></button>
        <Link className="note-float-icon" to="/notes" title="자유 노트 화면" aria-label="자유 노트 화면" onClick={() => void flush()}><Icon.external /></Link>
        <button type="button" className="note-float-icon" onClick={onClose} title="닫기" aria-label="닫기"><Icon.x /></button>
      </header>
      {title ? (
        <button
          type="button"
          className="note-float-lecture"
          title={title}
          disabled={!active && !!list?.length}
          // 누르는 순간 편집기의 커서·선택을 잃지 않게 한다.
          onMouseDown={(ev) => ev.preventDefault()}
          onClick={insertLecture}
        >
          <Icon.plus /> <span>{title}</span>
        </button>
      ) : null}
      <div className="note-float-body">
        {loadError ? <p className="notes-status is-bad" role="alert">{loadError}</p> : null}
        {saveState === 'failed' ? (
          <p className="notes-status is-bad" role="alert">
            저장 실패 · <button onClick={() => void flush()}>다시 시도</button>
          </p>
        ) : null}
        {active ? (
          <NoteEditor key={active.id} note={active} update={update} userId={userId} handle={handle} />
        ) : list && !list.length ? (
          <div className="notes-empty">
            <button className="notes-new" onClick={() => void create()} disabled={busy}><Icon.plus /> 새 노트</button>
          </div>
        ) : null}
      </div>
    </section>
  );
}
