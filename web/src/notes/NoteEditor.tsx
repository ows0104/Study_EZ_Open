import { useEffect, useLayoutEffect, useRef, useState, type ClipboardEvent as ReactClipboardEvent, type KeyboardEvent as ReactKeyboardEvent, type ReactNode } from 'react';
import { Icon } from '../shell/icons';
import type { NoteBlock, NoteBlockType } from '../types/notes';
import { sanitizeNoteHtml } from './sanitize';

/**
 * 자유 노트 편집기(2026-11-05 사용자 지시: Notion 게시물처럼 md로 쓰고 글자색·하이라이트를 칠한다).
 * 프로토타입 `redesign-prototype/notes.tsx`를 옮겼다. 2026-11-07 사용자 지시로 「강의」 칸은 자유 「태그」다.
 *
 * 블록마다 contentEditable 하나. React는 블록 목록·종류만 그리고 글 내용(DOM)은 건드리지 않는다.
 * 코드가 내용을 바꿔야 할 때(합치기·종류 전환)만 rev를 올려 블록을 다시 만든다.
 */

type BlockType = NoteBlockType;
export type Block = NoteBlock & { rev: number };
export type EditNote = { id: string; title: string; tags: string[]; blocks: Block[]; updatedAt: string };

const uid = () => Math.random().toString(36).slice(2, 10);
export const mk = (type: BlockType, html = '', extra: Partial<Block> = {}): Block => ({ id: uid(), type, html, rev: 0, ...extra });

const MAX_TAGS = 30;
const MAX_TAG_LEN = 40;
/** 「기본」 색: 이 표식 색으로 칠한 뒤 색 지정을 걷어 내 테마 글자색·바탕을 따르게 한다. */
const PLAIN_MARK = 'rgb(1, 2, 3)';

const TYPES: { type: BlockType; label: string; hint: string; keys: string; md?: string; glyph: string }[] = [
  { type: 'text', label: '텍스트', hint: '일반 문단', keys: 'text p 텍스트 문단', glyph: 'Aa' },
  { type: 'h1', label: '제목 1', hint: '큰 제목', keys: 'h1 heading 제목1 큰제목', md: '#', glyph: 'H1' },
  { type: 'h2', label: '제목 2', hint: '중간 제목', keys: 'h2 heading 제목2', md: '##', glyph: 'H2' },
  { type: 'h3', label: '제목 3', hint: '작은 제목', keys: 'h3 heading 제목3', md: '###', glyph: 'H3' },
  { type: 'bullet', label: '글머리 기호 목록', hint: '순서 없는 목록', keys: 'bullet list ul 글머리 목록', md: '-', glyph: '•' },
  { type: 'number', label: '번호 목록', hint: '순서 있는 목록', keys: 'number ol list 번호 목록', md: '1.', glyph: '1.' },
  { type: 'todo', label: '할 일 목록', hint: '체크 상자', keys: 'todo check 할일 체크', md: '[]', glyph: '☐' },
  { type: 'quote', label: '인용', hint: '인용문', keys: 'quote 인용', md: '>', glyph: '❝' },
  { type: 'callout', label: '콜아웃', hint: '눈에 띄는 상자', keys: 'callout 콜아웃 강조 상자', glyph: '💡' },
  { type: 'code', label: '코드', hint: '고정폭 글꼴', keys: 'code 코드', md: '```', glyph: '</>' },
  { type: 'divider', label: '구분선', hint: '가로줄', keys: 'divider hr 구분선 줄', md: '---', glyph: '—' },
];

/** 글자색·배경색. 흰 바탕에서 읽히도록 채도를 낮춘 열 가지. */
const COLORS = [
  { name: '기본', fg: '', bg: '' },
  { name: '회색', fg: '#7c7c7c', bg: '#efefed' },
  { name: '갈색', fg: '#8c5f45', bg: '#f3ece8' },
  { name: '주황', fg: '#c46a1d', bg: '#fbecdd' },
  { name: '노랑', fg: '#b58300', bg: '#fbf3d4' },
  { name: '초록', fg: '#3f7d55', bg: '#e7f2ea' },
  { name: '파랑', fg: '#2f6ea8', bg: '#e4eff8' },
  { name: '보라', fg: '#7a52b0', bg: '#f1eaf8' },
  { name: '분홍', fg: '#b2427c', bg: '#f9e8f1' },
  { name: '빨강', fg: '#c13f37', bg: '#fbe6e4' },
];

export function formatUpdated(iso: string) {
  const d = iso ? new Date(iso) : null;
  if (!d || Number.isNaN(d.getTime())) return '';
  return `${d.getMonth() + 1}월 ${d.getDate()}일 ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
}

/** 붙여넣기는 서식 없는 글로 넣는다(다른 곳의 글꼴·크기·스크립트를 들이지 않는다). */
function pastePlain(ev: ReactClipboardEvent<HTMLDivElement>) {
  ev.preventDefault();
  const text = ev.clipboardData.getData('text/plain');
  if (text) document.execCommand('insertText', false, text);
}

/* ───────── 커서 ───────── */

const plain = (el: HTMLElement) => (el.textContent ?? '').replace(/​/g, '');

function caretOffset(el: HTMLElement): number | null {
  const sel = getSelection();
  if (!sel || !sel.rangeCount) return null;
  const r = sel.getRangeAt(0);
  if (!el.contains(r.startContainer)) return null;
  const pre = document.createRange();
  pre.selectNodeContents(el);
  pre.setEnd(r.startContainer, r.startOffset);
  return pre.toString().length;
}

function atEnd(el: HTMLElement) {
  const sel = getSelection();
  if (!sel || !sel.rangeCount || !sel.isCollapsed) return false;
  const r = sel.getRangeAt(0);
  const post = document.createRange();
  post.selectNodeContents(el);
  post.setStart(r.endContainer, r.endOffset);
  return post.toString().replace(/​/g, '') === '';
}

/** 글자 수 기준 위치로 커서를 둔다. */
function placeCaret(el: HTMLElement, at: number | 'end') {
  el.focus();
  const sel = getSelection();
  if (!sel) return;
  const r = document.createRange();
  if (at === 'end') {
    r.selectNodeContents(el);
    r.collapse(false);
  } else {
    let left = at;
    let placed = false;
    const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
    for (let node = walker.nextNode(); node; node = walker.nextNode()) {
      const len = (node as Text).data.length;
      if (left <= len) {
        r.setStart(node, left);
        placed = true;
        break;
      }
      left -= len;
    }
    if (!placed) r.selectNodeContents(el);
    r.collapse(!placed ? at === 0 : true);
  }
  sel.removeAllRanges();
  sel.addRange(r);
}

/** 블록 맨 앞에서 n글자를 지운다(md 기호 제거용). */
function deleteLeading(el: HTMLElement, n: number) {
  const r = document.createRange();
  r.setStart(el, 0);
  let left = n;
  const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
  for (let node = walker.nextNode(); node; node = walker.nextNode()) {
    const len = (node as Text).data.length;
    if (left <= len) {
      r.setEnd(node, left);
      break;
    }
    left -= len;
  }
  r.deleteContents();
}

const clean = (el: HTMLElement) => {
  // 비우면 브라우저가 <br>을 남겨 빈 칸 안내 글이 안 보인다.
  if (plain(el) === '' && !el.querySelector('img')) el.innerHTML = '';
  return el.innerHTML;
};

/* md 줄머리 기호 → 블록 종류 */
const LINE_MD: [RegExp, BlockType, boolean?][] = [
  [/^###\s/, 'h3'],
  [/^##\s/, 'h2'],
  [/^#\s/, 'h1'],
  [/^[-*+]\s/, 'bullet'],
  [/^1[.)]\s/, 'number'],
  [/^\[x\]\s/i, 'todo', true],
  [/^\[\s?\]\s/, 'todo'],
  [/^[>"]\s/, 'quote'],
  [/^```/, 'code'],
];

/* 글 안 md: **굵게**, *기울임*, ~~취소선~~, `코드` */
const INLINE_MD: [RegExp, string][] = [
  [/\*\*([^*]+)\*\*$/, 'b'],
  [/~~([^~]+)~~$/, 's'],
  [/`([^`]+)`$/, 'code'],
  [/\*([^*\s][^*]*)\*$/, 'i'],
];

/* ───────── 편집 칸 하나 ───────── */

function Editable({ block, className, placeholder, register, onInput, onKeyDown }: {
  block: Block;
  className: string;
  placeholder: string;
  register: (id: string, el: HTMLDivElement | null) => void;
  onInput: (block: Block, el: HTMLDivElement, composing: boolean) => void;
  onKeyDown: (block: Block, el: HTMLDivElement, ev: ReactKeyboardEvent<HTMLDivElement>) => void;
}) {
  const ref = useRef<HTMLDivElement>(null);
  useLayoutEffect(() => {
    if (ref.current) ref.current.innerHTML = sanitizeNoteHtml(block.html);
    register(block.id, ref.current);
    return () => register(block.id, null);
    // 내용은 처음 만들 때만 넣는다. 바꿀 때는 부모가 rev로 다시 만든다.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  return (
    <div
      ref={ref}
      data-id={block.id}
      className={`nb-text ${className}`}
      contentEditable
      suppressContentEditableWarning
      spellCheck={false}
      data-placeholder={placeholder}
      onInput={(ev) => onInput(block, ev.currentTarget, (ev.nativeEvent as InputEvent).isComposing)}
      onKeyDown={(ev) => onKeyDown(block, ev.currentTarget, ev)}
      onPaste={pastePlain}
    />
  );
}

/* ───────── 편집기 ───────── */

type Slash = { blockId: string; node: Text; start: number; query: string; x: number; y: number; index: number };
type Bar = { x: number; y: number; bottom: number; states: Record<string, boolean>; blockId: string };
type FocusReq = { id: string; at: number | 'end' };

export function NoteEditor({ note, update }: { note: EditNote; update: (fn: (n: EditNote) => EditNote) => void }) {
  const els = useRef(new Map<string, HTMLDivElement>());
  const focusReq = useRef<FocusReq | null>(null);
  const titleRef = useRef<HTMLDivElement>(null);
  const editorRef = useRef<HTMLDivElement>(null);
  const [slash, setSlash] = useState<Slash | null>(null);
  const [bar, setBar] = useState<Bar | null>(null);
  const [colorOpen, setColorOpen] = useState(false);
  const [turnOpen, setTurnOpen] = useState(false);
  const [blockMenu, setBlockMenu] = useState<{ id: string; x: number; y: number } | null>(null);
  const [drag, setDrag] = useState<{ id: string; over?: string; after?: boolean } | null>(null);
  const blocks = note.blocks;

  const register = (id: string, el: HTMLDivElement | null) => {
    if (el) els.current.set(id, el);
    else els.current.delete(id);
  };

  // 제목은 노트를 바꿀 때만 다시 넣는다.
  useLayoutEffect(() => {
    if (titleRef.current) titleRef.current.textContent = note.title;
  }, [note.id]); // eslint-disable-line react-hooks/exhaustive-deps

  // 렌더 뒤 요청된 위치로 커서를 옮긴다.
  useLayoutEffect(() => {
    const req = focusReq.current;
    if (!req) return;
    const el = els.current.get(req.id);
    if (el) {
      placeCaret(el, req.at);
      focusReq.current = null;
    }
  });

  const setBlocks = (fn: (bs: Block[]) => Block[]) => update((n) => ({ ...n, blocks: fn(n.blocks) }));
  const patch = (id: string, p: Partial<Block>, bump = false) =>
    setBlocks((bs) => bs.map((b) => (b.id === id ? { ...b, ...p, rev: bump ? b.rev + 1 : b.rev } : b)));
  const insertAfter = (id: string, block: Block, focus: number | 'end' = 0) => {
    setBlocks((bs) => {
      const i = bs.findIndex((b) => b.id === id);
      return [...bs.slice(0, i + 1), block, ...bs.slice(i + 1)];
    });
    if (block.type !== 'divider') focusReq.current = { id: block.id, at: focus };
  };
  const convert = (block: Block, type: BlockType, html?: string) => {
    if (type === 'divider') {
      const next = mk('text');
      setBlocks((bs) => bs.flatMap((b) => (b.id === block.id ? [{ ...b, type, html: '', rev: b.rev + 1 }, next] : [b])));
      focusReq.current = { id: next.id, at: 0 };
      return;
    }
    patch(block.id, { type, html: html ?? els.current.get(block.id)?.innerHTML ?? block.html, checked: false }, true);
    focusReq.current = { id: block.id, at: 'end' };
  };

  /* 입력: md 변환·빗금 메뉴 */
  const onInput = (block: Block, el: HTMLDivElement, composing: boolean) => {
    const html = clean(el);
    if (!composing) {
      const text = plain(el).replace(/ /g, ' ');
      const offset = caretOffset(el) ?? 0;
      if (block.type === 'text' && text === '---') {
        convert(block, 'divider');
        return;
      }
      if (block.type === 'text') {
        for (const [re, type, checked] of LINE_MD) {
          const m = text.match(re);
          if (m && offset === m[0].length) {
            deleteLeading(el, m[0].length);
            patch(block.id, { type, html: clean(el), checked: !!checked }, true);
            focusReq.current = { id: block.id, at: 0 };
            setSlash(null);
            return;
          }
        }
      }
      const sel = getSelection();
      const node = sel?.anchorNode;
      if (node && node.nodeType === Node.TEXT_NODE && el.contains(node) && block.type !== 'code') {
        const t = node as Text;
        const before = t.data.slice(0, sel!.anchorOffset);
        for (const [re, tag] of INLINE_MD) {
          const m = before.match(re);
          if (!m) continue;
          const from = before.length - m[0].length;
          if (tag === 'i' && before[from - 1] === '*') continue;
          const r = document.createRange();
          r.setStart(t, from);
          r.setEnd(t, before.length);
          r.deleteContents();
          const wrap = document.createElement(tag);
          wrap.textContent = m[1];
          r.insertNode(wrap);
          // 굵게 등을 닫은 뒤 이어 쓰는 글이 바깥에 붙도록 빈 글자를 둔다.
          const tail = document.createTextNode('​');
          wrap.after(tail);
          const c = document.createRange();
          c.setStart(tail, 1);
          c.collapse(true);
          sel!.removeAllRanges();
          sel!.addRange(c);
          patch(block.id, { html: el.innerHTML });
          return;
        }
        // 빗금 메뉴 열기·검색어 갱신
        if (slash && slash.blockId === block.id && slash.node === t && sel!.anchorOffset > slash.start) {
          const query = t.data.slice(slash.start + 1, sel!.anchorOffset);
          if (/\s{2}/.test(query) || filterTypes(query).length === 0 && query.length > 2) setSlash(null);
          else setSlash({ ...slash, query, index: 0 });
        } else if (before.endsWith('/') && (before.length === 1 || /\s/.test(before[before.length - 2]))) {
          const rect = sel!.getRangeAt(0).getBoundingClientRect();
          const box = rect.width || rect.height ? rect : el.getBoundingClientRect();
          setSlash({ blockId: block.id, node: t, start: before.length - 1, query: '', x: box.left, y: box.bottom + 6, index: 0 });
        } else if (slash) {
          setSlash(null);
        }
      } else if (slash) {
        setSlash(null);
      }
    }
    patch(block.id, { html });
  };

  const filterTypes = (query: string) => {
    const q = query.trim().toLowerCase();
    return q ? TYPES.filter((t) => t.keys.toLowerCase().includes(q) || t.label.includes(q)) : TYPES;
  };

  const applySlash = (type: BlockType) => {
    if (!slash) return;
    const block = blocks.find((b) => b.id === slash.blockId);
    const el = els.current.get(slash.blockId);
    if (!block || !el) return;
    const r = document.createRange();
    r.setStart(slash.node, slash.start);
    r.setEnd(slash.node, Math.min(slash.node.data.length, slash.start + 1 + slash.query.length));
    r.deleteContents();
    const html = clean(el);
    setSlash(null);
    if (plain(el) === '') convert(block, type, '');
    else if (type === 'divider') {
      patch(block.id, { html });
      setBlocks((bs) => {
        const i = bs.findIndex((b) => b.id === block.id);
        return [...bs.slice(0, i + 1), mk('divider'), ...bs.slice(i + 1)];
      });
    } else {
      patch(block.id, { html });
      insertAfter(block.id, mk(type));
    }
  };

  /* 키: 줄 나누기·합치기·이동 */
  const onKeyDown = (block: Block, el: HTMLDivElement, ev: ReactKeyboardEvent<HTMLDivElement>) => {
    const native = ev.nativeEvent;
    if (native.isComposing || native.keyCode === 229) return;
    const i = blocks.findIndex((b) => b.id === block.id);

    if (slash) {
      const list = filterTypes(slash.query);
      if (ev.key === 'ArrowDown' || ev.key === 'ArrowUp') {
        ev.preventDefault();
        const d = ev.key === 'ArrowDown' ? 1 : -1;
        setSlash({ ...slash, index: (slash.index + d + list.length) % Math.max(1, list.length) });
        return;
      }
      if (ev.key === 'Enter' && list.length) {
        ev.preventDefault();
        applySlash(list[slash.index].type);
        return;
      }
      if (ev.key === 'Escape') {
        ev.preventDefault();
        setSlash(null);
        return;
      }
    }

    if (ev.key === 'Enter' && !ev.shiftKey) {
      ev.preventDefault();
      if (block.type === 'code') {
        document.execCommand('insertText', false, '\n');
        return;
      }
      const listy = block.type === 'bullet' || block.type === 'number' || block.type === 'todo';
      if ((listy || block.type === 'quote' || block.type === 'callout') && plain(el) === '') {
        convert(block, 'text', '');
        return;
      }
      const sel = getSelection();
      if (!sel || !sel.rangeCount) return;
      const r = sel.getRangeAt(0);
      r.deleteContents();
      const rest = document.createRange();
      rest.selectNodeContents(el);
      rest.setStart(r.startContainer, r.startOffset);
      const holder = document.createElement('div');
      holder.appendChild(rest.extractContents());
      const tailHtml = plain(holder) === '' ? '' : holder.innerHTML;
      patch(block.id, { html: clean(el) });
      insertAfter(block.id, mk(listy ? block.type : 'text', tailHtml));
      return;
    }

    if (ev.key === 'Backspace' && getSelection()?.isCollapsed && caretOffset(el) === 0) {
      if (block.type !== 'text') {
        ev.preventDefault();
        convert(block, 'text');
        focusReq.current = { id: block.id, at: 0 };
        return;
      }
      const prev = blocks[i - 1];
      if (!prev) return;
      ev.preventDefault();
      if (prev.type === 'divider') {
        setBlocks((bs) => bs.filter((b) => b.id !== prev.id));
        focusReq.current = { id: block.id, at: 0 };
        return;
      }
      const prevEl = els.current.get(prev.id);
      const joinAt = prevEl ? plain(prevEl).length : 0;
      const merged = (prevEl ? clean(prevEl) : prev.html) + clean(el);
      setBlocks((bs) => bs.filter((b) => b.id !== block.id).map((b) => (b.id === prev.id ? { ...b, html: merged, rev: b.rev + 1 } : b)));
      focusReq.current = { id: prev.id, at: joinAt };
      return;
    }

    const move = (dir: -1 | 1) => {
      for (let j = i + dir; j >= 0 && j < blocks.length; j += dir) {
        const el2 = els.current.get(blocks[j].id);
        if (el2) {
          ev.preventDefault();
          placeCaret(el2, dir < 0 ? 'end' : 0);
          return;
        }
      }
    };
    if (ev.key === 'ArrowUp' && caretOffset(el) === 0) move(-1);
    if (ev.key === 'ArrowDown' && atEnd(el)) move(1);
  };

  /* 글을 고르면 위에 서식 막대 */
  useEffect(() => {
    const onSel = () => {
      const sel = getSelection();
      if (!sel || sel.isCollapsed || !sel.rangeCount) {
        setBar(null);
        setColorOpen(false);
        setTurnOpen(false);
        return;
      }
      const r = sel.getRangeAt(0);
      const host = r.commonAncestorContainer;
      const el = (host.nodeType === Node.TEXT_NODE ? host.parentElement : (host as HTMLElement))?.closest<HTMLElement>('.nb-text');
      if (!el || !editorRef.current?.contains(el)) {
        setBar(null);
        return;
      }
      const rect = r.getBoundingClientRect();
      const states: Record<string, boolean> = {};
      for (const cmd of ['bold', 'italic', 'underline', 'strikeThrough']) states[cmd] = document.queryCommandState(cmd);
      setBar({ x: rect.left + rect.width / 2, y: rect.top, bottom: rect.bottom, states, blockId: el.dataset.id ?? '' });
    };
    document.addEventListener('selectionchange', onSel);
    return () => document.removeEventListener('selectionchange', onSel);
  }, []);

  const exec = (cmd: string, value?: string) => {
    document.execCommand('styleWithCSS', false, 'true');
    document.execCommand(cmd, false, value);
  };
  /** 「기본」 색: 표식 색으로 칠한 뒤 그 지정을 지워 테마 글자색·바탕을 따르게 한다(어두운 화면에서도 읽힌다). */
  const resetColor = (prop: 'color' | 'background-color') => {
    exec(prop === 'color' ? 'foreColor' : 'hiliteColor', PLAIN_MARK);
    const el = bar ? els.current.get(bar.blockId) : null;
    if (!el) return;
    el.querySelectorAll<HTMLElement>('[style]').forEach((node) => {
      if (node.style.getPropertyValue(prop) === PLAIN_MARK) node.style.removeProperty(prop);
      if (!node.getAttribute('style')?.trim()) node.removeAttribute('style');
      if (node.tagName === 'SPAN' && !node.attributes.length) node.replaceWith(...Array.from(node.childNodes));
    });
    el.dispatchEvent(new Event('input', { bubbles: true }));
  };
  const wrapCode = () => {
    const sel = getSelection();
    if (!sel || !sel.rangeCount) return;
    const r = sel.getRangeAt(0);
    const code = document.createElement('code');
    code.appendChild(r.extractContents());
    r.insertNode(code);
    const el = code.closest<HTMLElement>('.nb-text');
    el?.dispatchEvent(new Event('input', { bubbles: true }));
  };

  /* 블록 끌어 옮기기 */
  const onDrop = () => {
    if (!drag?.over || drag.over === drag.id) {
      setDrag(null);
      return;
    }
    setBlocks((bs) => {
      const moving = bs.find((b) => b.id === drag.id)!;
      const rest = bs.filter((b) => b.id !== drag.id);
      const at = rest.findIndex((b) => b.id === drag.over) + (drag.after ? 1 : 0);
      return [...rest.slice(0, at), moving, ...rest.slice(at)];
    });
    setDrag(null);
  };

  let counter = 0;
  const rows = blocks.map((block) => {
    counter = block.type === 'number' ? counter + 1 : 0;
    const no = counter;
    const editable = (cls: string, ph: string) => (
      <Editable key={`${block.id}:${block.rev}`} block={block} className={cls} placeholder={ph} register={register} onInput={onInput} onKeyDown={onKeyDown} />
    );
    let body: ReactNode;
    switch (block.type) {
      case 'h1':
      case 'h2':
      case 'h3':
        body = editable(`is-${block.type}`, `제목 ${block.type.slice(1)}`);
        break;
      case 'bullet':
        body = <div className="nb-list"><span className="nb-marker">•</span>{editable('', '목록')}</div>;
        break;
      case 'number':
        body = <div className="nb-list"><span className="nb-marker is-number">{no}.</span>{editable('', '목록')}</div>;
        break;
      case 'todo':
        body = (
          <div className={`nb-list${block.checked ? ' is-checked' : ''}`}>
            <button className="nb-check" aria-pressed={!!block.checked} aria-label="완료 표시" onClick={() => patch(block.id, { checked: !block.checked })}>
              {block.checked ? <svg viewBox="0 0 16 16" width="12" height="12"><path d="m3.5 8.5 3 3 6-7" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" /></svg> : null}
            </button>
            {editable('', '할 일')}
          </div>
        );
        break;
      case 'quote':
        body = <div className="nb-quote">{editable('', '인용')}</div>;
        break;
      case 'callout':
        body = <div className="nb-callout"><span className="nb-callout-icon">💡</span>{editable('', '내용')}</div>;
        break;
      case 'code':
        body = <div className="nb-code">{editable('', '코드')}</div>;
        break;
      case 'divider':
        body = <div className="nb-divider"><hr /></div>;
        break;
      default:
        body = editable('', "'/'를 입력해 블록 고르기");
    }
    const dropCls = drag?.over === block.id && drag.id !== block.id ? (drag.after ? ' is-drop-after' : ' is-drop-before') : '';
    return (
      <div
        key={block.id}
        className={`nb-row is-${block.type}${dropCls}${drag?.id === block.id ? ' is-dragging' : ''}`}
        onDragOver={(ev) => {
          if (!drag) return;
          ev.preventDefault();
          const rect = ev.currentTarget.getBoundingClientRect();
          const after = ev.clientY > rect.top + rect.height / 2;
          if (drag.over !== block.id || drag.after !== after) setDrag({ ...drag, over: block.id, after });
        }}
        onDrop={(ev) => {
          ev.preventDefault();
          onDrop();
        }}
      >
        <div className="nb-gutter">
          <button
            className="nb-handle"
            title="아래에 블록 추가"
            onClick={() => {
              const next = mk('text');
              insertAfter(block.id, next);
            }}
          >
            <Icon.plus />
          </button>
          <button
            className="nb-handle"
            title="끌어서 옮기기 · 눌러서 메뉴"
            draggable
            onDragStart={(ev) => {
              ev.dataTransfer.effectAllowed = 'move';
              ev.dataTransfer.setData('text/plain', block.id);
              setDrag({ id: block.id });
            }}
            onDragEnd={() => setDrag(null)}
            onClick={(ev) => {
              const r = ev.currentTarget.getBoundingClientRect();
              setBlockMenu({ id: block.id, x: r.left, y: r.bottom + 4 });
            }}
          >
            <svg viewBox="0 0 16 16" width="14" height="14" fill="currentColor"><circle cx="5.5" cy="3.5" r="1.3" /><circle cx="10.5" cy="3.5" r="1.3" /><circle cx="5.5" cy="8" r="1.3" /><circle cx="10.5" cy="8" r="1.3" /><circle cx="5.5" cy="12.5" r="1.3" /><circle cx="10.5" cy="12.5" r="1.3" /></svg>
          </button>
        </div>
        <div className="nb-body">{body}</div>
      </div>
    );
  });

  const slashList = slash ? filterTypes(slash.query) : [];
  const menuBlock = blockMenu ? blocks.find((b) => b.id === blockMenu.id) : null;
  const barBlock = bar ? blocks.find((b) => b.id === bar.blockId) : null;

  return (
    <div className="nb-editor" ref={editorRef}>
      <div
        ref={titleRef}
        className="nb-title"
        contentEditable
        suppressContentEditableWarning
        spellCheck={false}
        data-placeholder="제목 없음"
        onInput={(ev) => {
          const title = ev.currentTarget.textContent ?? '';
          if (!title) ev.currentTarget.innerHTML = '';
          update((n) => ({ ...n, title }));
        }}
        onPaste={pastePlain}
        onKeyDown={(ev) => {
          if (ev.key === 'Enter' && !ev.nativeEvent.isComposing) {
            ev.preventDefault();
            const first = blocks.find((b) => b.type !== 'divider');
            const el = first && els.current.get(first.id);
            if (el) placeCaret(el, 0);
          }
        }}
      />
      <dl className="nb-props">
        <div>
          <dt><Icon.tag /> 태그</dt>
          <dd><TagEditor tags={note.tags} onChange={(tags) => update((n) => ({ ...n, tags }))} /></dd>
        </div>
        <div>
          <dt><Icon.calendar /> 수정</dt>
          <dd className="nb-prop-text">{formatUpdated(note.updatedAt)}</dd>
        </div>
      </dl>

      <div className="nb-blocks">{rows}</div>
      <button className="nb-append" onClick={() => {
        const last = blocks[blocks.length - 1];
        const lastEl = last && els.current.get(last.id);
        if (last && last.type === 'text' && lastEl && plain(lastEl) === '') placeCaret(lastEl, 0);
        else {
          const next = mk('text');
          setBlocks((bs) => [...bs, next]);
          focusReq.current = { id: next.id, at: 0 };
        }
      }} aria-label="끝에 이어 쓰기" />

      {slash && slashList.length ? (
        <div className="nb-pop nb-slash" style={{ left: slash.x, top: slash.y }} role="listbox" onMouseDown={(e) => e.preventDefault()}>
          <div className="nb-pop-title">{slash.query ? `「${slash.query}」` : '기본 블록'}</div>
          {slashList.map((t, idx) => (
            <button key={t.type} role="option" aria-selected={idx === slash.index} className="nb-pop-item" onMouseEnter={() => setSlash({ ...slash, index: idx })} onClick={() => applySlash(t.type)}>
              <span className="nb-glyph">{t.glyph}</span>
              <span className="nb-pop-text"><b>{t.label}</b><small>{t.hint}</small></span>
              {t.md ? <kbd>{t.md}</kbd> : null}
            </button>
          ))}
        </div>
      ) : null}

      {bar ? (
        <div className="nb-bar" style={{ left: bar.x, top: Math.max(8, bar.y - 46) }} onMouseDown={(e) => e.preventDefault()}>
          <button className="nb-bar-turn" onClick={() => { setTurnOpen((v) => !v); setColorOpen(false); }}>
            {TYPES.find((t) => t.type === barBlock?.type)?.label ?? '텍스트'} <span className="nb-caret">▾</span>
          </button>
          <i className="nb-bar-sep" />
          <button className={bar.states.bold ? 'is-on' : ''} onClick={() => exec('bold')} title="굵게 (Ctrl B)"><b>B</b></button>
          <button className={bar.states.italic ? 'is-on' : ''} onClick={() => exec('italic')} title="기울임 (Ctrl I)"><i style={{ fontFamily: 'Georgia, serif' }}>i</i></button>
          <button className={bar.states.underline ? 'is-on' : ''} onClick={() => exec('underline')} title="밑줄 (Ctrl U)"><u>U</u></button>
          <button className={bar.states.strikeThrough ? 'is-on' : ''} onClick={() => exec('strikeThrough')} title="취소선"><s>S</s></button>
          <button onClick={wrapCode} title="코드"><span className="nb-bar-code">{'</>'}</span></button>
          <i className="nb-bar-sep" />
          <button className="nb-bar-color" onClick={() => { setColorOpen((v) => !v); setTurnOpen(false); }} title="글자색·배경색">
            <span className="nb-bar-a">A</span> <span className="nb-caret">▾</span>
          </button>
          {colorOpen ? (
            <div className="nb-pop nb-colors">
              <div className="nb-pop-title">글자 색</div>
              <div className="nb-color-grid">
                {COLORS.map((c) => (
                  <button key={`fg-${c.name}`} title={`${c.name} 글자`} onClick={() => (c.fg ? exec('foreColor', c.fg) : resetColor('color'))}>
                    <span className="nb-color-chip" style={c.fg ? { color: c.fg } : undefined}>A</span>
                  </button>
                ))}
              </div>
              <div className="nb-pop-title">배경 색</div>
              <div className="nb-color-grid">
                {COLORS.map((c) => (
                  <button key={`bg-${c.name}`} title={`${c.name} 배경`} onClick={() => (c.bg ? exec('hiliteColor', c.bg) : resetColor('background-color'))}>
                    <span className="nb-color-chip is-bg" style={c.bg ? { background: c.bg } : undefined} />
                  </button>
                ))}
              </div>
            </div>
          ) : null}
          {turnOpen && barBlock ? (
            <div className="nb-pop nb-turn">
              <div className="nb-pop-title">전환</div>
              {TYPES.filter((t) => t.type !== 'divider').map((t) => (
                <button key={t.type} className="nb-pop-item" aria-selected={t.type === barBlock.type} onClick={() => { setTurnOpen(false); convert(barBlock, t.type); }}>
                  <span className="nb-glyph">{t.glyph}</span>
                  <span className="nb-pop-text"><b>{t.label}</b></span>
                </button>
              ))}
            </div>
          ) : null}
        </div>
      ) : null}

      {blockMenu && menuBlock ? (
        <>
          <div className="nb-scrim" onClick={() => setBlockMenu(null)} />
          <div className="nb-pop nb-block-menu" style={{ left: blockMenu.x, top: blockMenu.y }}>
            <button className="nb-pop-item" onClick={() => {
              setBlocks((bs) => (bs.length > 1 ? bs.filter((b) => b.id !== menuBlock.id) : [mk('text')]));
              setBlockMenu(null);
            }}><span className="nb-glyph"><Icon.x /></span><span className="nb-pop-text"><b>삭제</b></span><kbd>Del</kbd></button>
            <button className="nb-pop-item" onClick={() => {
              const el = els.current.get(menuBlock.id);
              insertAfter(menuBlock.id, mk(menuBlock.type, el?.innerHTML ?? menuBlock.html, { checked: menuBlock.checked }), 'end');
              setBlockMenu(null);
            }}><span className="nb-glyph"><Icon.layers /></span><span className="nb-pop-text"><b>복제</b></span></button>
            <div className="nb-pop-title">전환</div>
            {TYPES.map((t) => (
              <button key={t.type} className="nb-pop-item" aria-selected={t.type === menuBlock.type} onClick={() => { convert(menuBlock, t.type); setBlockMenu(null); }}>
                <span className="nb-glyph">{t.glyph}</span>
                <span className="nb-pop-text"><b>{t.label}</b></span>
              </button>
            ))}
          </div>
        </>
      ) : null}
    </div>
  );
}

/* ───────── 태그(2026-11-07 사용자 지시: 「강의」 칸 대신 자유롭게 쓰는 태그) ───────── */

function TagEditor({ tags, onChange }: { tags: string[]; onChange: (tags: string[]) => void }) {
  const [draft, setDraft] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const editing = draft !== null;
  useEffect(() => {
    if (editing) inputRef.current?.focus();
  }, [editing]);

  const addAll = (raws: string[]) => {
    const next = [...tags];
    for (const raw of raws) {
      const tag = raw.split(/\s+/).filter(Boolean).join(' ').slice(0, MAX_TAG_LEN);
      if (tag && !next.includes(tag) && next.length < MAX_TAGS) next.push(tag);
    }
    if (next.length !== tags.length) onChange(next);
  };
  const remove = (tag: string) => onChange(tags.filter((t) => t !== tag));

  return (
    <>
      {tags.map((t) => (
        <span key={t} className="nb-prop-chip nb-tag">
          {t}
          <button className="nb-tag-x" aria-label={`${t} 태그 삭제`} onClick={() => remove(t)}><Icon.x /></button>
        </span>
      ))}
      {editing ? (
        <input
          ref={inputRef}
          className="nb-tag-input"
          value={draft}
          maxLength={MAX_TAG_LEN}
          aria-label="새 태그"
          onChange={(ev) => {
            const parts = ev.target.value.split(/[,，]/);
            if (parts.length > 1) addAll(parts.slice(0, -1));
            setDraft(parts[parts.length - 1]);
          }}
          onKeyDown={(ev) => {
            if (ev.nativeEvent.isComposing) return;
            if (ev.key === 'Enter') {
              ev.preventDefault();
              addAll([draft]);
              setDraft('');
            } else if (ev.key === 'Escape') {
              setDraft(null);
            } else if (ev.key === 'Backspace' && draft === '' && tags.length) {
              remove(tags[tags.length - 1]);
            }
          }}
          onBlur={() => {
            addAll([draft]);
            setDraft(null);
          }}
        />
      ) : !tags.length ? <span className="nb-prop-empty">비어 있음</span> : null}
      {!editing && tags.length < MAX_TAGS ? (
        <button className="nb-prop-add" title="태그 추가" aria-label="태그 추가" onClick={() => setDraft('')}><Icon.plus /></button>
      ) : null}
    </>
  );
}
