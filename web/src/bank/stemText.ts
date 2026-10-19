/** Remove transport wrappers before splitting blanks; keep authored wording intact. */
export function stemText(text: string): string {
  return text.replace(/<\/?escape\s*>/gi, "")
    .replace(/(`+)(\{\{c\d+\}\})\1/g, "$2");
}
