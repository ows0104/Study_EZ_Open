/** Layout metadata only; never rewrite stored question or answer text. */
export function textLayout(line: string) {
  const spaces = line.match(/^[ \t]*/)?.[0].replace(/\t/g, "    ").length ?? 0;
  // A period after a letter can be an abbreviation (e.g. C. difficile).
  const list = /^(?:\*\*)?(?:[-*+•●▪◦–—]|\d+[.)]|[A-Za-z가-힣]\)|[①-⑳])(?:\*\*)?[ \t]+/.test(line.trimStart());
  return { list, style: spaces ? { marginInlineStart: `${spaces / 2}em` } : undefined };
}
