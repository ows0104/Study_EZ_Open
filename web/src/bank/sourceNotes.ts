/** Read explicit source-comparison rows without guessing their medical meaning. */
export function sourceNote(text: string) {
  const cleaned = text.replace(/<Cite\b[^>]*\/>/gi, "").replace(/cite[^]*/g, "").trim();
  const rows: { label: string; text: string }[] = [];
  let structured = true;
  for (const line of cleaned.split(/\r?\n/).filter(line => line.trim())) {
    const match = line.match(/^\s*(판단|자료\s+\d+|근거|미해결)\s*[:：]\s*(.*)$/);
    if (match) rows.push({ label: match[1].replace(/\s+/g, " "), text: match[2].trim() });
    else if (rows.length) rows[rows.length - 1].text += `\n${line.trim()}`;
    else structured = false;
  }
  structured &&= rows.some(row => row.label === "판단") && rows.some(row => row.label.startsWith("자료 "))
    && rows.some(row => row.label === "근거") && rows.every(row => row.text.length > 0);
  return { text: cleaned, rows: structured ? rows : [], pending: structured ? rows.find(row => row.label === "미해결")?.text : undefined };
}
