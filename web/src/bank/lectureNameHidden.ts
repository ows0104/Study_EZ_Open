import { useState } from 'react';

/**
 * 모아풀기 「강의명 숨기기」(docs/changes/2026-11-24-hide-lecture-names, 사용자 「강의명 자체가 힌트인 문제가 많아서」).
 * 복습퀴즈·족보 모아풀기가 같은 값을 쓴다. 처음은 꺼짐(강의명 보임).
 */
const KEY = 'studyez:mix-hide-lecture';

function read(): boolean {
  try { return localStorage.getItem(KEY) === 'on'; } catch { return false; }
}

export function useLectureNameHidden(): [boolean, () => void] {
  const [hidden, setHidden] = useState(read);
  const toggle = () => {
    const next = !hidden;
    try { localStorage.setItem(KEY, next ? 'on' : 'off'); } catch { /* 이번 화면에서는 고른 대로 동작한다. */ }
    setHidden(next);
  };
  return [hidden, toggle];
}
