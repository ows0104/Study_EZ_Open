import { useCallback, useState } from "react";

/**
 * 한 번 누른 화면 토글을 이 브라우저에 기억한다(2026-11-11 사용자 지시: 그 사람이 누른 값이 기본으로 유지).
 * 저장값이 없거나 허용값이 아니거나 저장소를 못 쓰면 fallback. 저장이 막혀도 이번 화면에서는 고른 대로 동작한다.
 */
export function readPreference<T extends string>(key: string, fallback: T, allowed: readonly T[]): T {
  try {
    const value = localStorage.getItem(key);
    return value !== null && (allowed as readonly string[]).includes(value) ? (value as T) : fallback;
  } catch {
    return fallback;
  }
}

export function savePreference(key: string, value: string) {
  try { localStorage.setItem(key, value); } catch { /* 이번 화면에서만 유지 */ }
}

export function usePreference<T extends string>(key: string, fallback: T, allowed: readonly T[]) {
  const [value, setValue] = useState<T>(() => readPreference(key, fallback, allowed));
  const change = useCallback((next: T) => { setValue(next); savePreference(key, next); }, [key]);
  return [value, change] as const;
}

const FLAG = ["1", "0"] as const;

/** 켜짐/꺼짐 토글. "1"/"0"으로 저장한다(좌측 메뉴 접기의 기존 형식). */
export function useFlagPreference(key: string, fallback = false) {
  const [value, change] = usePreference<"1" | "0">(key, fallback ? "1" : "0", FLAG);
  const set = useCallback((on: boolean) => change(on ? "1" : "0"), [change]);
  return [value === "1", set] as const;
}
