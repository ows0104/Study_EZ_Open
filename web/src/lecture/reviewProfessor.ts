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
  return [
    `복습 담당 교수 확인: ${filename}`,
    names.length ? `올해 필기 파일명에 적힌 교수: ${names.join("·")}. 시간표나 족보의 올해 담당 표기와 다르면 이 파일명을 우선해 확인해줘.`
      : "올해 필기 파일명에서 담당 교수를 확정할 수 없어. 강의자료의 명시된 담당을 확인하고, 확인되지 않으면 교수 미상으로 남겨줘.",
    "족보는 각 연도 옆의 교수와 대조해 실제 올해 담당 교수의 기출부터 우선하고, 다른 교수·교수 미상 기출은 참고로 사용해줘. 첨부 PDF의 정렬이 시간표 기준이면 실제 필기 교수로 우선순위를 다시 판단해줘.",
  ].join("\n");
}
