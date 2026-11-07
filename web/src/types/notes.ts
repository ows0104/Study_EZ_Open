// 자유 노트 API(`/api/me/notes`). 서버 server/app/routes/notes.py와 같은 모양.

export type NoteBlockType =
  | "text" | "h1" | "h2" | "h3" | "bullet" | "number" | "todo" | "quote" | "callout" | "code" | "divider";

export type NoteBlock = { id: string; type: NoteBlockType; html: string; checked?: boolean };

export type NoteSummary = { id: string; title: string; tags: string[]; updatedAt: string };

export type Note = NoteSummary & { blocks: NoteBlock[] };

export type NoteInput = { title: string; tags: string[]; blocks: NoteBlock[] };
