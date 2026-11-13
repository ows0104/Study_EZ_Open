import { useEffect, useRef, useState } from "react";

/** 학습 화면을 브라우저 전체 화면으로. 문서 전체를 올려 대화창·노트도 그대로 보인다. */
export function FullscreenButton() {
  const [active, setActive] = useState(() => Boolean(document.fullscreenElement));
  // 이 버튼이 켠 전체 화면만 학습 화면을 떠날 때 끈다.
  const entered = useRef(false);

  useEffect(() => {
    const sync = () => {
      const on = Boolean(document.fullscreenElement);
      if (!on) entered.current = false;
      setActive(on);
    };
    document.addEventListener("fullscreenchange", sync);
    return () => {
      document.removeEventListener("fullscreenchange", sync);
      if (entered.current && document.fullscreenElement) void document.exitFullscreen().catch(() => {});
    };
  }, []);

  // iPhone Safari 등은 요소 전체 화면을 지원하지 않는다.
  if (!document.fullscreenEnabled) return null;

  const toggle = () => {
    if (document.fullscreenElement) {
      void document.exitFullscreen().catch(() => {});
      return;
    }
    document.documentElement
      .requestFullscreen()
      .then(() => { entered.current = true; })
      .catch(() => {});
  };

  return <button type="button" className="is-quiet" aria-pressed={active} onClick={toggle}>
    {active ? "전체 화면 끝" : "전체 화면"}
  </button>;
}
