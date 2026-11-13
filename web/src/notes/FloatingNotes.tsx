import { Suspense, lazy, useState } from 'react';
import { useLocation } from 'react-router-dom';
import { Icon } from '../shell/icons';
import './floating-notes.css';

/**
 * 우측 하단 자유 노트 버튼(2026-11-13 사용자 지시). 어느 화면에서든 떠나지 않고 노트 창을 띄운다.
 * 창은 셸에 붙어 있어 경로가 바뀌어도 그대로다. `/notes`에서는 그 화면이 노트라 띄우지 않는다.
 * 편집기는 무거워 창을 처음 열 때 받는다.
 */
const FloatingNotePanel = lazy(() => import('./FloatingNotePanel'));

export function FloatingNotes({ userId, lecture }: { userId: string; lecture: string | null }) {
  const { pathname } = useLocation();
  const [open, setOpen] = useState(false);
  if (pathname === '/notes') return null;
  return (
    <>
      {open ? (
        <Suspense fallback={null}>
          <FloatingNotePanel userId={userId} lecture={lecture} pathname={pathname} onClose={() => setOpen(false)} />
        </Suspense>
      ) : null}
      <button
        type="button"
        className={`note-fab${open ? ' is-open' : ''}`}
        aria-label={open ? '자유 노트 닫기' : '자유 노트'}
        aria-expanded={open}
        title="자유 노트"
        onClick={() => setOpen((v) => !v)}
      >
        {open ? <Icon.x /> : <Icon.note />}
      </button>
    </>
  );
}
