import { createContext, useContext, useEffect } from 'react';

/**
 * 퀴즈 화면이 지금 푸는 강의명을 셸에 알린다. 플로팅 노트의 「＋강의명」 버튼이 본문 커서 자리에 넣는다(2026-11-13).
 * 알리지 않는 화면은 노트 창이 주소의 강의에서 이름을 읽는다(`FloatingNotePanel`).
 */
export const NoteLecture = createContext<(title: string | null) => void>(() => {});

export function useNoteLecture(title: string | null | undefined) {
  const set = useContext(NoteLecture);
  useEffect(() => {
    set(title || null);
    return () => set(null);
  }, [title, set]);
}
