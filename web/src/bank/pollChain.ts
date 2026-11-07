export type TimerHandle = ReturnType<typeof setTimeout>;
export type Timers = {
  setTimeout: (fn: () => void, ms: number) => TimerHandle;
  clearTimeout: (handle: TimerHandle) => void;
};

const realTimers: Timers = { setTimeout: (fn, ms) => setTimeout(fn, ms), clearTimeout: handle => clearTimeout(handle) };

/**
 * 앞 요청이 끝난 뒤에 다음 요청을 센다. 멈추는 함수를 돌려준다.
 *
 * 고정 간격(`setInterval`)은 응답이 간격보다 오래 걸리면 요청을 겹쳐 쌓는다. 운영
 * 2026-11-07 로그에서 관리자 `GET …/generation`은 따뜻한 인스턴스에서도 2.0–6.3초였고
 * 화면은 3초마다 쳤다 — 쌓인 요청이 CPU 하나짜리 인스턴스를 포화시켜, 뒤늦은 스케일아웃의
 * 콜드스타트가 학생의 Main-Quiz 요청에 얹혔다.
 *
 * `run`은 자기 오류를 스스로 처리한다. 거절되어도 사슬은 멈추지 않는다 — 한 번의 실패로
 * 진행 중 작업의 추적을 놓지 않는다.
 */
export function pollAfterSettled(run: () => Promise<unknown>, delayMs: number, timers: Timers = realTimers) {
  let live = true;
  let handle = timers.setTimeout(tick, delayMs);
  function tick() {
    void Promise.resolve()
      .then(run)
      .catch(() => {})
      .then(() => { if (live) handle = timers.setTimeout(tick, delayMs); });
  }
  return () => { live = false; timers.clearTimeout(handle); };
}
