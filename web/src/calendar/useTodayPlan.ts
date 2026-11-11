import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "../api";
import type { ExamPlan, StudyPlan } from "../types/studyPlan";
import { useStudyTarget } from "./useStudyTarget";

/**
 * 「오늘 복습」 칸의 분모(2026-11-11 사용자 지시): 시험까지 오늘의 학습 목표(`/api/study-plan`)에서
 * 가장 가까운 시험의 하루 확보 목표(%p). 시험 목표는 「시험까지 오늘의 학습 목표」 판과 같은 값을 쓴다.
 * 판처럼 창으로 돌아올 때와 5분마다 다시 부른다. 실패·시험 없음은 null.
 */
export function useTodayPlan(): { plan: ExamPlan | null; loading: boolean } {
  const [target] = useStudyTarget();
  const [plan, setPlan] = useState<ExamPlan | null>(null);
  const [loading, setLoading] = useState(true);
  const [refresh, setRefresh] = useState(0);
  const reload = useCallback(() => setRefresh(v => v + 1), []);
  useEffect(() => {
    let live = true;
    api<StudyPlan>(`/api/study-plan?target=${target}`)
      .then(value => { if (live) setPlan(value.plans[0] ?? null); })
      .catch((cause: Error) => { if (live && !(cause instanceof ApiError && cause.status === 404)) setPlan(null); })
      .finally(() => { if (live) setLoading(false); });
    return () => { live = false; };
  }, [target, refresh]);
  useEffect(() => {
    const tick = () => { if (document.visibilityState === "visible") reload(); };
    window.addEventListener("focus", reload);
    const timer = window.setInterval(tick, 5 * 60_000);
    return () => { window.removeEventListener("focus", reload); window.clearInterval(timer); };
  }, [reload]);
  return { plan, loading };
}
