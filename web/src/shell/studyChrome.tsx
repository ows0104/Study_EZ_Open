import { createContext, useContext, useEffect } from "react";

/**
 * Main-Quiz 주소는 시작 화면과 풀이 화면이 같다(2026-11-08).
 * 새 Main-Quiz(뿌리 학습)는 풀이까지 홈과 같은 좌측 메뉴 안에 선다 — 이 신호를 쓰지 않는다.
 * 같은 주소의 기존 Quiz Bank 화면만 푸는 동안 창 전체를 쓰겠다고 알린다.
 */
export const StudyChrome = createContext<(solving: boolean) => void>(() => {});

export function useSolvingChrome(solving: boolean) {
  const set = useContext(StudyChrome);
  useEffect(() => {
    set(solving);
    return () => set(false);
  }, [solving, set]);
}

/** 시작 화면을 좌측 메뉴 안에 두는 Main-Quiz 주소. 전체 문제·연결 학습 등 다른 하위 화면은 그대로 둔다. */
export const isMainQuizPath = (path: string) =>
  /^\/(bank|mainquiz)\/[^/]+\/[^/]+(\/roots)?\/?$/.test(path);
