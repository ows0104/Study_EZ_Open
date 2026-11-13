// 자유 노트 API(`/api/me/notes`). 서버 server/app/routes/notes.py와 같은 모양.

export type NoteBlockType =
  | "text" | "h1" | "h2" | "h3" | "bullet" | "number" | "todo" | "quote" | "callout" | "code" | "divider" | "image";

/** image 블록: `image`는 이 브라우저(IndexedDB)에 둔 사진의 id. 사진 바이트는 서버로 보내지 않는다(2026-11-13). */
export type NoteBlock = { id: string; type: NoteBlockType; html: string; checked?: boolean; image?: string };

export type NoteSummary = { id: string; title: string; tags: string[]; updatedAt: string };

export type Note = NoteSummary & { blocks: NoteBlock[] };

export type NoteInput = { title: string; tags: string[]; blocks: NoteBlock[] };
