import { useCallback, useEffect, useState } from "react";
import { api } from "../api";

/**
 * Optional 계산 제외(2026-11-13 사용자 지시, docs/changes/2026-11-13-exclude-optional).
 * 계정 단위로 서버에 저장하고, 서버가 학습률·카드 수·목표 요약을 계산할 때 읽는다(쿼리로 보내지 않는다).
 * 바뀌면 `OPTIONAL_EVENT`를 보내 이미 그려진 화면(강의 목록·패널·캘린더·오늘 복습)이 다시 읽게 한다.
 */
export const OPTIONAL_EVENT = "studyez-optional-exclusion";
const PATH = "/api/root-learning/optional";

let current: boolean | null = null;
let loading: Promise<boolean> | null = null;
let version = 0;

function load(): Promise<boolean> {
  if (current !== null) return Promise.resolve(current);
  loading ??= api<{ exclude: boolean }>(PATH)
    .then(v => { current = Boolean(v.exclude); return current; })
    .catch(() => { loading = null; return false; });
  return loading;
}

function announce(value: boolean) {
  current = value;
  version += 1;
  window.dispatchEvent(new CustomEvent(OPTIONAL_EVENT, { detail: value }));
}

/** 토글 값과 바꾸기. 저장이 실패하면 앞 값으로 돌아간다. */
export function useOptionalExclusion() {
  const [value, setValue] = useState<boolean | null>(current);
  const [saving, setSaving] = useState(false);
  useEffect(() => {
    let live = true;
    void load().then(v => { if (live) setValue(v); });
    const onChange = (event: Event) => setValue((event as CustomEvent<boolean>).detail);
    window.addEventListener(OPTIONAL_EVENT, onChange);
    return () => { live = false; window.removeEventListener(OPTIONAL_EVENT, onChange); };
  }, []);
  const change = useCallback(async (next: boolean) => {
    const before = current ?? false;
    setValue(next); setSaving(true);
    try {
      const saved = await api<{ exclude: boolean }>(PATH, {
        method: "PUT", body: JSON.stringify({ requestId: crypto.randomUUID(), exclude: next }),
      });
      announce(Boolean(saved.exclude));
    } catch {
      setValue(before);
    } finally {
      setSaving(false);
    }
  }, []);
  return { exclude: value, saving, change };
}

/** 토글이 바뀔 때마다 오르는 수. 학습률·카드 수를 읽는 effect의 의존성에 넣는다. */
export function useOptionalVersion(): number {
  const [value, setValue] = useState(version);
  useEffect(() => {
    const onChange = () => setValue(version);
    window.addEventListener(OPTIONAL_EVENT, onChange);
    return () => window.removeEventListener(OPTIONAL_EVENT, onChange);
  }, []);
  return value;
}
