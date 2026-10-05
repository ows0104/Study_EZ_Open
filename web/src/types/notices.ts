/** 공지 한 건(`GET /api/notices`). 고정이 먼저, 그 안에서 새 글이 먼저 온다. */
export type Notice = {
  id: number;
  title: string;
  body: string;
  pinned: boolean;
  createdAt: string | null;
  updatedAt: string | null;
};
