/** Chrome 버전은 1~4개의 숫자로 구성된다. 생략된 자리는 0으로 비교한다. */
export function versionAtLeast(version: string, minimum: string) {
  const parse = (value: string) => /^\d+(?:\.\d+){0,3}$/.test(value)
    ? value.split(".").map(Number) : null;
  const installed = parse(version);
  const required = parse(minimum);
  if (!installed || !required) return false;
  for (let i = 0; i < 4; i += 1) {
    const difference = (installed[i] ?? 0) - (required[i] ?? 0);
    if (difference) return difference > 0;
  }
  return true;
}

export const PREVIEW_MIN_VERSION = "1.2.0";
export const AUTO_SEND_MIN_VERSION = "1.3.3";
export const BANK_AUTO_SEND_MIN_VERSION = "1.3.9";
/** 확장이 복습 결과 종류를 직접 구분하기 시작한 버전. 구버전은 사이트에서 구분한다. */
export const NATIVE_REVIEW_MIN_VERSION = "1.3.5";

export type BridgeMode = "shared" | "personal" | "review" | "bank";

/** 1.2는 직접 전송한다. 1.3.0~1.3.2는 수동 요청도 자동 전송하므로 갱신이 필요하다. */
export function minimumVersionForInput(installed: string, mode: BridgeMode, autoSend: boolean) {
  if (mode === "bank" && autoSend) return BANK_AUTO_SEND_MIN_VERSION;
  if (autoSend || versionAtLeast(installed, "1.3.0")) return AUTO_SEND_MIN_VERSION;
  return PREVIEW_MIN_VERSION;
}
