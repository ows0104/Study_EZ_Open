import { useSyncExternalStore } from "react";

const KEY = "studyez-study-target";
const EVENT = "studyez-study-target-change";

function read() {
  try {
    const value = Number(localStorage.getItem(KEY));
    return [70, 80, 90, 95, 100].includes(value) ? value : 90;
  } catch { return 90; }
}

function subscribe(notify: () => void) {
  window.addEventListener("storage", notify);
  window.addEventListener(EVENT, notify);
  return () => {
    window.removeEventListener("storage", notify);
    window.removeEventListener(EVENT, notify);
  };
}

export function useStudyTarget(): [number, (value: number) => void] {
  const target = useSyncExternalStore(subscribe, read);
  return [target, value => {
    try { localStorage.setItem(KEY, String(value)); } catch { return; }
    window.dispatchEvent(new Event(EVENT));
  }];
}
