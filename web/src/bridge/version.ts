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

export const PREVIEW_MIN_VERSION = "1.3.3";
export const REVIEW_MIN_VERSION = "1.3.5";
