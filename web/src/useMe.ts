import { useEffect, useState } from "react";
import { api } from "./api";
import type { Me } from "./types";

/**
 * 지금 로그인한 사람.
 *
 * 껍데기(`App`)가 이미 한 번 받지만 거기서 패널까지 내려보내려면 캘린더를 통째로
 * 지나야 한다. 값이 바뀌지 않으므로 모듈에 한 번만 받아 둔다 — 칸을 옮겨 다닐
 * 때마다 요청이 나가지 않는다.
 *
 * **화면을 가르는 데만 쓴다.** 권한은 서버가 정한다 — 관리자가 아닌 사람이
 * 기본 링크를 저장하려 들면 `PUT /api/admin/…`이 403으로 막는다.
 */
let cached: Me | null = null;
const waiting = new Set<(value: Me) => void>();

export function useMe() {
  const [me, setMe] = useState<Me | null>(cached);

  useEffect(() => {
    if (cached) return;
    waiting.add(setMe);
    api<Me>("/api/me")
      .then((next) => {
        cached = next;
        waiting.forEach((notify) => notify(next));
        waiting.clear();
      })
      .catch(() => waiting.delete(setMe));
    return () => void waiting.delete(setMe);
  }, []);

  return me;
}
