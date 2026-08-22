import { useEffect, useState } from "react";
import { getMe, peekMe } from "./firstScreen";
import type { Me } from "./types";

/**
 * 지금 로그인한 사람.
 *
 * 껍데기(`App`)가 이미 한 번 받지만 거기서 패널까지 내려보내려면 캘린더를 통째로
 * 지나야 한다. 받아 둔 것을 같이 쓴다 — 껍데기와 여기가 따로 부르면 같은
 * `/api/me`가 두 번 나간다(실제로 그러고 있었다).
 *
 * **화면을 가르는 데만 쓴다.** 권한은 서버가 정한다 — 관리자가 아닌 사람이
 * 기본 링크를 저장하려 들면 `PUT /api/admin/…`이 403으로 막는다.
 */
export function useMe() {
  const [me, setMe] = useState<Me | null>(peekMe);

  useEffect(() => {
    if (me) return;
    let alive = true;
    getMe()
      .then((value) => {
        if (alive) setMe(value);
      })
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, [me]);

  return me;
}
