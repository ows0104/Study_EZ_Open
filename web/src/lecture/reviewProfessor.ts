/** Read only an explicit professor group before the note writer suffix. */
export function professorsFromNotesFilename(filename: string): string[] {
  // Run IDs contain an underscore. Strip their bracketed prefix before the writer.
  const lecture = filename.normalize("NFKC").replace(/^\s*\[[^\]]+\]\s*/, "").split(/[_＿]/)[0];
  const groups = [...lecture.matchAll(/\(([^()]*)\)/g)];
  for (const match of groups.reverse()) {
    const group = match[1].trim();
    if (!/^[가-힣\s,·ㆍ/]+$/.test(group)) continue;
    const names = group.split(/[\s,·ㆍ/]+/).filter(Boolean).flatMap(name =>
      name.length === 6 || name.length === 9 ? name.match(/.{3}/g)! : [name]);
    if (names.length && names.every(name => name.length >= 2 && name.length <= 4)) return [...new Set(names)];
  }
  return [];
}

export function reviewProfessorGuidance(filename: string) {
  const names = professorsFromNotesFilename(filename);
  return `올해 담당 교수: ${names.length ? names.join("·") : "교수 미상"}`;
}
