/** 짧은 요약을 우선 쓰되, 옛 은행의 전체 제목도 단어 단위로 최대 세 줄까지 보여 준다. */
export function graphLabel(title: string, measure: (text: string) => number): string[] {
  const maxWidth = 88;
  const lines: string[] = [];
  let line = "";
  const tokens = title.trim().replace(/\s+/g, " ").split(/(?<=\s|[·/,:：])/u);
  for (const token of tokens) {
    if (measure((line + token).trim()) <= maxWidth) {
      line += token;
      continue;
    }
    if (line.trim()) lines.push(line.trim());
    line = "";
    // 한 줄보다 긴 단일 용어만 글자 경계에서 나눈다. 영문은 글자 수 대신 실제 폭으로 잰다.
    for (const char of token.trimStart()) {
      if (measure(line + char) > maxWidth && line) {
        lines.push(line.trim());
        line = "";
      }
      line += char;
    }
  }
  if (line.trim()) lines.push(line.trim());
  if (lines.length <= 3) return lines;
  let last = lines[2];
  while (measure(`${last}…`) > maxWidth) last = Array.from(last).slice(0, -1).join("");
  return [lines[0], lines[1], `${last.trimEnd()}…`];
}
