import { useMe } from '../useMe';
import { Icon } from '../shell/icons';
import { NoteEditor, formatUpdated } from './NoteEditor';
import { useNoteStore } from './useNoteStore';
import './notes.css';

/**
 * 자유 노트(`/notes`). 왼쪽 목록, 오른쪽 편집기. 노트는 계정별로 서버(`/api/me/notes`)에 둔다.
 * 목록·저장은 플로팅 노트 창과 같은 `useNoteStore`를 쓴다. 사진은 이 브라우저에만 둔다(`localImages`).
 */

export function NotesPage() {
  const userId = useMe()?.id ?? '';
  const { list, loadError, activeId, active, saveState, busy, flush, update, select, create, remove } = useNoteStore({ userId });

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
          <br /><kbd>Tab</kbd> 들여쓰기 · <kbd>Ctrl D</kbd> 복제 · <kbd>Ctrl Shift ↑↓</kbd> 옮기기 · <kbd>Ctrl Z</kbd> 되돌리기
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
          <NoteEditor key={active.id} note={active} update={update} userId={userId} />
        ) : list && !list.length ? (
          <div className="notes-empty">
            <button className="notes-new" onClick={() => void create()} disabled={busy}><Icon.plus /> 새 노트</button>
          </div>
        ) : null}
      </div>
    </div>
  );
}
