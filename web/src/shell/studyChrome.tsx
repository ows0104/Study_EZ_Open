import { createContext, useContext, useEffect } from "react";

/**
 * Main-Quiz는 시작 화면과 풀이 화면이 같은 주소다(2026-11-08).
 * 시작 화면은 홈과 같은 좌측 메뉴 안에 서고, 문항을 푸는 동안만 창 전체를 쓴다.
 * 주소로는 둘을 가를 수 없어 화면이 직접 알린다.
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
