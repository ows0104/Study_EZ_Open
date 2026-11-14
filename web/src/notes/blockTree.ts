import type { NoteBlock, NoteBlockType } from '../types/notes';

/**
 * 자유 노트 블록 나무(2026-11-14). 블록은 평평한 배열이고, 한 블록 뒤에 이어지는 더 깊은 `indent` 블록이 그 하위다.
 * 들여쓰기·접기·옮기기·번호·붙여넣기 해석을 DOM 없이 계산한다.
 */

export const MAX_INDENT = 6;
export const MAX_TABLE_ROWS = 100;
export const MAX_TABLE_COLS = 20;

type Tree = Pick<NoteBlock, 'type' | 'indent' | 'open'>;

export const depth = (b: Pick<NoteBlock, 'indent'>) => Math.max(0, Math.min(MAX_INDENT, b.indent ?? 0));

/** i번 블록과 그 하위가 끝나는 위치(배타). */
export function subtreeEnd(blocks: Tree[], i: number): number {
  const d = depth(blocks[i]);
  let j = i + 1;
  while (j < blocks.length && depth(blocks[j]) > d) j++;
  return j;
}

export const hasChildren = (blocks: Tree[], i: number) => subtreeEnd(blocks, i) > i + 1;

/** 접힌 토글 아래라서 그리지 않을 블록의 위치. */
export function hiddenIndexes(blocks: Tree[]): Set<number> {
  const hidden = new Set<number>();
  let below: number | null = null;
  blocks.forEach((b, i) => {
    const d = depth(b);
    if (below !== null && d > below) {
      hidden.add(i);
      return;
    }
    below = b.type === 'toggle' && b.open === false ? d : null;
  });
  return hidden;
}

const BULLETS = ['•', '◦', '▪'];

function alpha(n: number): string {
  let s = '';
  for (let k = n; k > 0; k = Math.floor((k - 1) / 26)) s = String.fromCharCode(97 + ((k - 1) % 26)) + s;
  return s;
}

function roman(n: number): string {
  const table: [number, string][] = [[1000, 'm'], [900, 'cm'], [500, 'd'], [400, 'cd'], [100, 'c'], [90, 'xc'],
    [50, 'l'], [40, 'xl'], [10, 'x'], [9, 'ix'], [5, 'v'], [4, 'iv'], [1, 'i']];
  let s = '';
  let k = n;
  for (const [v, r] of table) while (k >= v) { s += r; k -= v; }
  return s;
}

/** 목록 표식: 단계마다 • ◦ ▪, 1. a. i. 를 돌려 쓴다. 번호는 같은 부모·같은 단계 안에서 이어 센다. */
export function listMarkers(blocks: Tree[]): string[] {
  const counters: number[] = [];
  return blocks.map((b) => {
    const d = depth(b);
    counters.length = d + 1;
    if (b.type === 'number') {
      counters[d] = (counters[d] ?? 0) + 1;
      const n = counters[d];
      const style = d % 3;
      return `${style === 0 ? n : style === 1 ? alpha(n) : roman(n)}.`;
    }
    counters[d] = 0;
    return b.type === 'bullet' ? BULLETS[d % 3] : '';
  });
}

/** Tab(+1)·Shift+Tab(-1): 하위와 함께 옮긴다. 할 수 없으면 null. */
export function shiftIndent<T extends Tree>(blocks: T[], i: number, delta: 1 | -1): T[] | null {
  const d = depth(blocks[i]);
  const end = subtreeEnd(blocks, i);
  if (delta > 0) {
    if (i === 0 || d > depth(blocks[i - 1])) return null;
    for (let j = i; j < end; j++) if (depth(blocks[j]) >= MAX_INDENT) return null;
  } else if (d === 0) {
    return null;
  }
  return blocks.map((b, j) => (j >= i && j < end ? { ...b, indent: depth(b) + delta } : b));
}

/** 같은 단계의 앞(-1)·뒤(+1) 블록과 자리를 바꾼다(각자 하위 포함). 할 수 없으면 null. */
export function moveSibling<T extends Tree>(blocks: T[], i: number, dir: -1 | 1): T[] | null {
  const d = depth(blocks[i]);
  const end = subtreeEnd(blocks, i);
  if (dir < 0) {
    let j = i - 1;
    while (j >= 0 && depth(blocks[j]) > d) j--;
    if (j < 0 || depth(blocks[j]) !== d) return null;
    return [...blocks.slice(0, j), ...blocks.slice(i, end), ...blocks.slice(j, i), ...blocks.slice(end)];
  }
  if (end >= blocks.length || depth(blocks[end]) !== d) return null;
  const end2 = subtreeEnd(blocks, end);
  return [...blocks.slice(0, i), ...blocks.slice(end, end2), ...blocks.slice(i, end), ...blocks.slice(end2)];
}

/** 끌어 놓기: i번 블록(하위 포함)을 target 앞/뒤로, 놓는 자리 블록과 같은 단계로 옮긴다. */
export function moveTo<T extends Tree & { id: string }>(blocks: T[], i: number, targetId: string, after: boolean): T[] | null {
  const end = subtreeEnd(blocks, i);
  const moving = blocks.slice(i, end);
  if (moving.some((b) => b.id === targetId)) return null;
  const rest = [...blocks.slice(0, i), ...blocks.slice(end)];
  const t = rest.findIndex((b) => b.id === targetId);
  if (t < 0) return null;
  const at = after ? subtreeEnd(rest, t) : t;
  const shift = depth(rest[t]) - depth(moving[0]);
  const moved = moving.map((b) => ({ ...b, indent: Math.max(0, Math.min(MAX_INDENT, depth(b) + shift)) }));
  return [...rest.slice(0, at), ...moved, ...rest.slice(at)];
}

/* ───────── 붙여넣기 해석 ───────── */

export type PastedLine = { type: NoteBlockType; html: string; indent: number; checked?: boolean };
export type Pasted = { kind: 'lines'; lines: PastedLine[] } | { kind: 'table'; rows: string[][] };

export const escapeHtml = (text: string) => text.replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`);

/** 붙여넣은 글 안의 **굵게**, ~~취소~~, `코드`. 글자는 먼저 이스케이프한다. */
function inlineMd(text: string): string {
  return escapeHtml(text)
    .replace(/\*\*([^*]+)\*\*/g, '<b>$1</b>')
    .replace(/~~([^~]+)~~/g, '<s>$1</s>')
    .replace(/`([^`]+)`/g, '<code>$1</code>');
}

const LINE_PREFIX: [RegExp, NoteBlockType, boolean?][] = [
  [/^###\s+/, 'h3'],
  [/^##\s+/, 'h2'],
  [/^#\s+/, 'h1'],
  [/^\[[xX]\]\s+/, 'todo', true],
  [/^\[\s?\]\s+/, 'todo'],
  [/^[-*+•◦▪]\s+\[[xX]\]\s+/, 'todo', true],
  [/^[-*+•◦▪]\s+\[\s?\]\s+/, 'todo'],
  [/^[-*+•◦▪]\s+/, 'bullet'],
  [/^(\d+|[a-zA-Z])[.)]\s+/, 'number'],
  [/^>\s?/, 'quote'],
];

function leadingLevel(line: string): number {
  const lead = line.match(/^[ \t]*/)?.[0] ?? '';
  let spaces = 0;
  for (const ch of lead) spaces += ch === '\t' ? 2 : 1;
  return Math.floor(spaces / 2);
}

const clampTable = (rows: string[][]) => {
  const cut = rows.slice(0, MAX_TABLE_ROWS).map((r) => r.slice(0, MAX_TABLE_COLS));
  const cols = Math.max(1, ...cut.map((r) => r.length));
  return cut.map((r) => [...r, ...Array(cols - r.length).fill('')]);
};

/** 표처럼 보이는 글(엑셀·시트 TSV, md 표)이면 칸을 돌려준다. */
export function parseTable(text: string): string[][] | null {
  const lines = text.replace(/\r\n?/g, '\n').split('\n').filter((l) => l.trim() !== '');
  if (lines.length < 2) return null;
  // md 표: | a | b | 다음 줄 |---|---|
  const isRow = (l: string) => /^\s*\|.*\|\s*$/.test(l);
  if (lines.every(isRow) && /^\s*\|?\s*:?-{2,}/.test(lines[1])) {
    const cells = (l: string) => l.trim().replace(/^\|/, '').replace(/\|$/, '').split('|').map((c) => inlineMd(c.trim()));
    return clampTable([lines[0], ...lines.slice(2)].map(cells));
  }
  // TSV: 줄마다 칸 수가 같고, 줄머리 들여쓰기 탭만 있는 글은 아니다.
  const split = lines.map((l) => l.split('\t'));
  const cols = split[0].length;
  if (cols >= 2 && split.every((r) => r.length === cols) && lines.some((l) => /\S\t/.test(l))) {
    return clampTable(split.map((r) => r.map((c) => inlineMd(c.trim()))));
  }
  return null;
}

/** 여러 줄 글을 블록 줄로 나눈다. 빈 줄이 여러 개 이어지면 하나로 줄인다. */
export function parsePaste(text: string): Pasted {
  const table = parseTable(text);
  if (table) return { kind: 'table', rows: table };
  const raw = text.replace(/\r\n?/g, '\n').replace(/\n+$/, '').split('\n');
  const lines: PastedLine[] = [];
  let code: string[] | null = null;
  let codeIndent = 0;
  let blank = false;
  for (const line of raw) {
    if (code) {
      if (/^\s*```/.test(line)) {
        lines.push({ type: 'code', html: escapeHtml(code.join('\n')), indent: codeIndent });
        code = null;
      } else {
        code.push(line);
      }
      continue;
    }
    if (/^\s*```/.test(line)) {
      code = [];
      codeIndent = leadingLevel(line);
      blank = false;
      continue;
    }
    if (line.trim() === '') {
      if (!blank && lines.length) lines.push({ type: 'text', html: '', indent: 0 });
      blank = true;
      continue;
    }
    blank = false;
    const level = leadingLevel(line);
    let body = line.trimStart();
    let type: NoteBlockType = 'text';
    let checked: boolean | undefined;
    if (/^(-{3,}|\*{3,}|_{3,})$/.test(body.trim())) {
      lines.push({ type: 'divider', html: '', indent: level });
      continue;
    }
    for (const [re, t, c] of LINE_PREFIX) {
      const m = body.match(re);
      if (m) {
        type = t;
        checked = c;
        body = body.slice(m[0].length);
        break;
      }
    }
    lines.push({ type, html: inlineMd(body), indent: level, ...(type === 'todo' ? { checked: !!checked } : {}) });
  }
  if (code) lines.push({ type: 'code', html: escapeHtml(code.join('\n')), indent: codeIndent });
  if (lines.length && lines[lines.length - 1].type === 'text' && lines[lines.length - 1].html === '' && lines.length > 1) lines.pop();
  // 들여쓰기: 가장 얕은 줄을 0으로, 바로 위 줄보다 한 단계 넘게 깊어지지 않게.
  const filled = lines.filter((l) => l.html !== '' || l.type !== 'text');
  const base = filled.length ? Math.min(...filled.map((l) => l.indent)) : 0;
  let prev = -1;
  for (const l of lines) {
    if (l.type === 'text' && l.html === '') {
      l.indent = 0;
      continue;
    }
    l.indent = Math.max(0, Math.min(MAX_INDENT, l.indent - base, prev + 1));
    prev = l.indent;
  }
  return { kind: 'lines', lines };
}
