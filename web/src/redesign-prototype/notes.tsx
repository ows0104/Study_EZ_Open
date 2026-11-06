import { useEffect, useLayoutEffect, useMemo, useRef, useState, type KeyboardEvent as ReactKeyboardEvent, type ReactNode } from 'react';
import { Icon } from './icons';

/**
 * 자유 노트(2026-11-05 사용자 지시: Notion 게시물처럼 md로 쓰고 글자색·하이라이트를 칠한다).
 *
 * 블록마다 contentEditable 하나. React는 블록 목록·종류만 그리고 글 내용(DOM)은 건드리지 않는다.
 * 코드가 내용을 바꿔야 할 때(합치기·종류 전환)만 rev를 올려 블록을 다시 만든다.
 * 프로토타입에서는 localStorage에만 저장한다.
 */

type BlockType = 'text' | 'h1' | 'h2' | 'h3' | 'bullet' | 'number' | 'todo' | 'quote' | 'callout' | 'code' | 'divider';
type Block = { id: string; type: BlockType; html: string; checked?: boolean; rev: number };
type Note = { id: string; title: string; blocks: Block[]; updated: string; lectures: string[] };

const uid = () => Math.random().toString(36).slice(2, 10);
const mk = (type: BlockType, html = '', extra: Partial<Block> = {}): Block => ({ id: uid(), type, html, rev: 0, ...extra });

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

const today = () => {
  const d = new Date();
  return `${d.getMonth() + 1}월 ${d.getDate()}일 ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
};

const SEED: Note[] = [
  {
    id: 'seed-1',
    title: '1차 시험 정리 — 세균',
    updated: '11월 5일 09:40',
    lectures: ['6', '9', '10', '11', '12'],
    blocks: [
      mk('callout', '1차 시험 <b>11월 20일(금) 9:00</b> · 강의 1–48, TBL 1–2, CBL 1–6'),
      mk('h2', '그람양성 알균'),
      mk('bullet', '<b>포도알균</b>: coagulase 양성이면 <span style="color: #c13f37;">S. aureus</span>'),
      mk('bullet', '사슬알균은 용혈 양상(α·β·γ)으로 먼저 나눈다'),
      mk('h2', '장내세균'),
      mk('number', '젖당 발효 여부'),
      mk('number', '<span style="background-color: #fbf3d4;">H₂S 생성</span> — Salmonella, Proteus'),
      mk('number', '운동성'),
      mk('quote', '강의 11 요점: 기회감염균과 장병원성균을 따로 묶어 정리'),
      mk('h3', '할 일'),
      mk('todo', '강의 10 강의록 1회독', { checked: true }),
      mk('todo', '강의 11 예습 퀴즈 2회독'),
      mk('todo', '오류 토의 3건 확인'),
      mk('divider'),
      mk('text', ''),
    ],
  },
  {
    id: 'seed-2',
    title: 'TBL 2 준비 — 심내막염',
    updated: '11월 4일 22:15',
    lectures: ['TBL 2', '14'],
    blocks: [
      mk('h2', 'Duke criteria'),
      mk('bullet', '주 기준: 혈액 배양 양성, 심초음파 소견'),
      mk('bullet', '부 기준: 발열, 혈관 현상, 면역 현상, 소인'),
      mk('text', '동영상 강의 14를 먼저 보고 <span style="background-color: #e4eff8;">원인균별 경험적 치료</span>를 표로 만들 것.'),
    ],
  },
  { id: 'seed-3', title: '', updated: '11월 3일 18:02', lectures: [], blocks: [mk('text', '')] },
];

function loadNotes(): Note[] {
  try {
    const raw = localStorage.getItem('proto-notes');
    if (raw) return JSON.parse(raw) as Note[];
  } catch {
    /* 깨진 값이면 예시로 시작 */
  }
  return SEED;
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
    if (ref.current) ref.current.innerHTML = block.html;
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
    />
  );
}

/* ───────── 편집기 ───────── */

type Slash = { blockId: string; node: Text; start: number; query: string; x: number; y: number; index: number };
type Bar = { x: number; y: number; bottom: number; states: Record<string, boolean>; blockId: string };
type FocusReq = { id: string; at: number | 'end' };

function NoteEditor({ note, update }: { note: Note; update: (fn: (n: Note) => Note) => void }) {
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

  const setBlocks = (fn: (bs: Block[]) => Block[]) => update((n) => ({ ...n, blocks: fn(n.blocks), updated: today() }));
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
          update((n) => ({ ...n, title, updated: today() }));
        }}
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
          <dt><Icon.layers /> 강의</dt>
          <dd>
            {note.lectures.length ? note.lectures.map((l) => <span key={l} className="nb-prop-chip">{/^\d+$/.test(l) ? `강의 ${l}` : l}</span>) : <span className="nb-prop-empty">비어 있음</span>}
            <button className="nb-prop-add" title="강의 연결"><Icon.plus /></button>
          </dd>
        </div>
        <div>
          <dt><Icon.calendar /> 수정</dt>
          <dd className="nb-prop-text">{note.updated}</dd>
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
                  <button key={`fg-${c.name}`} title={`${c.name} 글자`} onClick={() => exec('foreColor', c.fg || '#171717')}>
                    <span className="nb-color-chip" style={{ color: c.fg || '#171717' }}>A</span>
                  </button>
                ))}
              </div>
              <div className="nb-pop-title">배경 색</div>
              <div className="nb-color-grid">
                {COLORS.map((c) => (
                  <button key={`bg-${c.name}`} title={`${c.name} 배경`} onClick={() => exec('hiliteColor', c.bg || 'transparent')}>
                    <span className="nb-color-chip is-bg" style={{ background: c.bg || '#fff' }} />
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

/* ───────── 화면 ───────── */

export function NotesPage() {
  const [notes, setNotes] = useState<Note[]>(loadNotes);
  const [activeId, setActiveId] = useState(() => notes[0]?.id ?? '');
  const active = notes.find((n) => n.id === activeId) ?? notes[0];

  useEffect(() => {
    const t = setTimeout(() => localStorage.setItem('proto-notes', JSON.stringify(notes)), 250);
    return () => clearTimeout(t);
  }, [notes]);

  const update = (fn: (n: Note) => Note) => setNotes((ns) => ns.map((n) => (n.id === active.id ? fn(n) : n)));
  const create = () => {
    const note: Note = { id: uid(), title: '', blocks: [mk('text')], updated: today(), lectures: [] };
    setNotes((ns) => [note, ...ns]);
    setActiveId(note.id);
  };
  const sorted = useMemo(() => notes, [notes]);

  return (
    <div className="notes-layout">
      <aside className="notes-list" aria-label="노트 목록">
        <div className="notes-list-head">
          <strong>자유 노트</strong>
          <button className="icon-button" onClick={create} title="새 노트" aria-label="새 노트"><Icon.plus /></button>
        </div>
        {sorted.map((n) => (
          <button key={n.id} className={`notes-item${n.id === active?.id ? ' is-active' : ''}`} onClick={() => setActiveId(n.id)}>
            <span className="notes-item-icon"><Icon.file /></span>
            <span className="notes-item-text">
              <b className={n.title ? '' : 'is-empty'}>{n.title || '제목 없음'}</b>
              <small>{n.updated}</small>
            </span>
          </button>
        ))}
        <p className="notes-hint">
          <kbd>/</kbd> 블록 고르기 · <kbd>#</kbd> <kbd>-</kbd> <kbd>[]</kbd> <kbd>&gt;</kbd> 줄머리 md · <kbd>**굵게**</kbd> <kbd>`코드`</kbd> · 글을 고르면 색·하이라이트
        </p>
      </aside>
      <div className="notes-main">
        {active ? <NoteEditor key={active.id} note={active} update={update} /> : null}
      </div>
    </div>
  );
}
