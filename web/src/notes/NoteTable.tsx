import { useLayoutEffect, useRef, useState, type ClipboardEvent as ReactClipboardEvent, type KeyboardEvent as ReactKeyboardEvent } from 'react';
import { MAX_TABLE_COLS, MAX_TABLE_ROWS, parseTable } from './blockTree';
import { sanitizeNoteHtml } from './sanitize';

/**
 * 자유 노트 표 블록(2026-11-14). 칸마다 contentEditable 하나.
 * 칸 내용은 처음 그릴 때만 넣고, 행·열을 바꾸면 부모가 rev를 올려 칸을 다시 만든다(편집기 글 칸과 같은 규칙).
 */

type Cell = { r: number; c: number };

export function NoteTable({ id, rev, rows, header, register, onChange, onExit }: {
  id: string;
  rev: number;
  rows: string[][];
  header: boolean;
  /** 첫 칸을 블록 id로 등록한다(편집기의 커서 옮기기·포커스 요청이 표에 들어올 때). */
  register: (id: string, el: HTMLDivElement | null) => void;
  /** structural이면 칸을 다시 만든다. */
  onChange: (rows: string[][], header: boolean, structural: boolean) => void;
  /** 표 맨 위/아래에서 위·아래 화살표 */
  onExit: (dir: -1 | 1) => void;
}) {
  const wrap = useRef<HTMLDivElement>(null);
  const [active, setActive] = useState<Cell | null>(null);
  const pending = useRef<Cell | null>(null);
  const cols = rows[0]?.length ?? 1;

  const cellEl = (r: number, c: number) => wrap.current?.querySelector<HTMLDivElement>(`[data-cell="${r}:${c}"]`) ?? null;
  const read = (): string[][] => rows.map((row, r) => row.map((_, c) => {
    const el = cellEl(r, c);
    if (!el) return rows[r][c];
    if ((el.textContent ?? '').replace(/​/g, '') === '') el.innerHTML = '';
    return el.innerHTML;
  }));

  // 칸 내용은 rev가 바뀔 때만 넣는다.
  useLayoutEffect(() => {
    rows.forEach((row, r) => row.forEach((html, c) => {
      const el = cellEl(r, c);
      if (el) el.innerHTML = sanitizeNoteHtml(html);
    }));
    register(id, cellEl(0, 0));
    const want = pending.current;
    if (want) {
      pending.current = null;
      focusCell(want.r, want.c, 'end');
    }
    return () => register(id, null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rev, rows.length, cols]);

  function focusCell(r: number, c: number, at: 'start' | 'end') {
    const el = cellEl(r, c);
    if (!el) return;
    el.focus();
    const sel = getSelection();
    if (!sel) return;
    const range = document.createRange();
    range.selectNodeContents(el);
    range.collapse(at === 'start');
    sel.removeAllRanges();
    sel.addRange(range);
  }

  const restructure = (next: string[][], focus: Cell, nextHeader = header) => {
    pending.current = focus;
    onChange(next, nextHeader, true);
  };

  const addRow = (after: number, focusCol = active?.c ?? 0) => {
    const current = read();
    if (current.length >= MAX_TABLE_ROWS) return;
    const next = [...current.slice(0, after + 1), Array(cols).fill(''), ...current.slice(after + 1)];
    restructure(next, { r: after + 1, c: focusCol });
  };
  const addCol = (after: number) => {
    if (cols >= MAX_TABLE_COLS) return;
    const next = read().map((row) => [...row.slice(0, after + 1), '', ...row.slice(after + 1)]);
    restructure(next, { r: active?.r ?? 0, c: after + 1 });
  };
  const dropRow = (r: number) => {
    const current = read();
    if (current.length <= 1) return;
    const next = current.filter((_, i) => i !== r);
    restructure(next, { r: Math.min(r, next.length - 1), c: active?.c ?? 0 });
  };
  const dropCol = (c: number) => {
    if (cols <= 1) return;
    const next = read().map((row) => row.filter((_, i) => i !== c));
    restructure(next, { r: active?.r ?? 0, c: Math.min(c, cols - 2) });
  };

  const onKeyDown = (r: number, c: number, ev: ReactKeyboardEvent<HTMLDivElement>) => {
    const native = ev.nativeEvent;
    if (native.isComposing || native.keyCode === 229) return;
    if (ev.ctrlKey || ev.metaKey || ev.altKey) return;
    const last = rows.length - 1;
    if (ev.key === 'Tab') {
      ev.preventDefault();
      ev.stopPropagation();
      if (ev.shiftKey) {
        if (c > 0) focusCell(r, c - 1, 'end');
        else if (r > 0) focusCell(r - 1, cols - 1, 'end');
        return;
      }
      if (c < cols - 1) focusCell(r, c + 1, 'end');
      else if (r < last) focusCell(r + 1, 0, 'end');
      else addRow(r, 0);
      return;
    }
    if (ev.key === 'Enter' && !ev.shiftKey) {
      ev.preventDefault();
      ev.stopPropagation();
      if (r < last) focusCell(r + 1, c, 'end');
      else addRow(r, c);
      return;
    }
    const onEdge = (dir: -1 | 1) => {
      const sel = getSelection();
      if (!sel || !sel.rangeCount || !sel.isCollapsed) return false;
      const caret = sel.getRangeAt(0).getBoundingClientRect();
      const box = ev.currentTarget.getBoundingClientRect();
      // 빈 칸이면 범위가 0이다: 칸 안에 줄이 하나뿐이라고 본다.
      if (!caret.height) return true;
      return dir < 0 ? caret.top - box.top < caret.height : box.bottom - caret.bottom < caret.height;
    };
    if (ev.key === 'ArrowUp' && onEdge(-1)) {
      ev.preventDefault();
      if (r > 0) focusCell(r - 1, c, 'end');
      else onExit(-1);
    } else if (ev.key === 'ArrowDown' && onEdge(1)) {
      ev.preventDefault();
      if (r < last) focusCell(r + 1, c, 'end');
      else onExit(1);
    }
  };

  /** 칸에 붙여넣기: 표처럼 생긴 글은 지금 칸부터 채우고(필요하면 늘림), 아니면 한 줄 글로. */
  const onPaste = (r: number, c: number, ev: ReactClipboardEvent<HTMLDivElement>) => {
    ev.preventDefault();
    ev.stopPropagation();
    const text = ev.clipboardData.getData('text/plain');
    if (!text) return;
    const grid = parseTable(text);
    if (!grid) {
      document.execCommand('insertText', false, text.replace(/\r?\n/g, ' '));
      return;
    }
    const current = read();
    const needRows = Math.min(MAX_TABLE_ROWS, Math.max(current.length, r + grid.length));
    const needCols = Math.min(MAX_TABLE_COLS, Math.max(cols, c + grid[0].length));
    const next = Array.from({ length: needRows }, (_, i) => Array.from({ length: needCols }, (_, j) => current[i]?.[j] ?? ''));
    grid.forEach((row, i) => row.forEach((html, j) => {
      if (r + i < needRows && c + j < needCols) next[r + i][c + j] = html;
    }));
    restructure(next, { r: Math.min(needRows - 1, r + grid.length - 1), c: Math.min(needCols - 1, c + grid[0].length - 1) });
  };

  const cellClass = (r: number) => `nb-text nb-cell${header && r === 0 ? ' is-head' : ''}`;

  return (
    <div className="nb-table-wrap" ref={wrap}>
      {active ? (
        <div className="nb-table-bar" onMouseDown={(e) => e.preventDefault()}>
          <button onClick={() => addRow(active.r)}>행 추가</button>
          <button onClick={() => addCol(active.c)}>열 추가</button>
          <button onClick={() => dropRow(active.r)} disabled={rows.length <= 1}>행 삭제</button>
          <button onClick={() => dropCol(active.c)} disabled={cols <= 1}>열 삭제</button>
          <button className={header ? 'is-on' : ''} aria-pressed={header} onClick={() => restructure(read(), active, !header)}>머리글</button>
        </div>
      ) : null}
      <div className="nb-table-scroll">
        <table className="nb-table">
          <tbody>
            {rows.map((row, r) => (
              <tr key={r}>
                {row.map((_, c) => (
                  <td key={`${r}:${c}:${rev}`} className={header && r === 0 ? 'is-head' : undefined}>
                    <div
                      data-cell={`${r}:${c}`}
                      data-id={id}
                      className={cellClass(r)}
                      contentEditable
                      suppressContentEditableWarning
                      spellCheck={false}
                      onFocus={() => setActive({ r, c })}
                      onBlur={(ev) => {
                        if (!wrap.current?.contains(ev.relatedTarget as Node | null)) setActive(null);
                      }}
                      onInput={() => onChange(read(), header, false)}
                      onKeyDown={(ev) => onKeyDown(r, c, ev)}
                      onPaste={(ev) => onPaste(r, c, ev)}
                    />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/** 새 표: 3×3, 첫 행 머리글. */
export const emptyTable = (): string[][] => [['', '', ''], ['', '', ''], ['', '', '']];
