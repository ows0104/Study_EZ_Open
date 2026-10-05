import { useCallback, useEffect, useState, type ReactNode } from "react";
import { api } from "../api";
import type { Notice } from "../types/notices";
import { markNoticeSeen } from "./seen";

/**
 * 공지사항. 승인된 사람은 읽고, 관리자는 같은 화면에서 쓰고 고친다.
 *
 * 2026-10-04 관리자 — 「슬슬 운영을 시작해서 공지사항하고 이용방법 탭을
 * 만들어야할 것 같아.」 **쓰는 자리를 `/admin` 탭으로 따로 두지 않았다.** 관리
 * 탭들은 파이프라인을 돌리는 자리이고, 공지는 쓴 것이 학생에게 어떻게 보이는지를
 * 그 자리에서 보는 편이 낫다.
 */
export function NoticesPage({ isAdmin, onSeen }: { isAdmin: boolean; onSeen: (latest: number) => void }) {
  const [notices, setNotices] = useState<Notice[] | null>(null);
  const [error, setError] = useState("");
  // 펼친 공지. 처음에는 맨 위 하나만 편다 — 들어온 이유가 대개 그 글이다.
  const [open, setOpen] = useState<Set<number>>(new Set());
  // 고치는 중인 공지. `0` 은 새 글이다.
  const [editing, setEditing] = useState<number | null>(null);

  const load = useCallback(() => {
    api<Notice[]>("/api/notices")
      .then((rows) => {
        setNotices(rows);
        setOpen((prev) => (prev.size || !rows.length ? prev : new Set([rows[0].id])));
        if (rows.length) {
          const latest = Math.max(...rows.map((row) => row.id));
          markNoticeSeen(latest);
          onSeen(latest);
        }
      })
      .catch((cause: Error) => setError(cause.message));
  }, [onSeen]);

  useEffect(load, [load]);

  function toggle(id: number) {
    setOpen((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  async function remove(notice: Notice) {
    if (!window.confirm(`「${notice.title}」을 지웁니다. 되돌릴 수 없습니다.`)) return;
    try {
      await api(`/api/admin/notices/${notice.id}`, { method: "DELETE" });
      load();
    } catch (cause) {
      setError((cause as Error).message);
    }
  }

  return (
    <div className="doc-page">
      <header className="doc-head">
        <h1>공지사항</h1>
        {isAdmin && editing === null ? (
          <button className="is-primary" onClick={() => setEditing(0)}>
            새 공지 쓰기
          </button>
        ) : null}
      </header>

      {error ? <p className="notice is-error">{error}</p> : null}

      {editing === 0 ? (
        <NoticeEditor
          onCancel={() => setEditing(null)}
          onSaved={(saved) => {
            setEditing(null);
            setOpen(new Set([saved.id]));
            load();
          }}
        />
      ) : null}

      {notices === null ? (
        error ? null : <p className="notice">불러오는 중…</p>
      ) : notices.length === 0 ? (
        <p className="doc-empty">아직 올라온 공지가 없습니다.</p>
      ) : (
        <ul className="notice-list">
          {notices.map((notice) =>
            editing === notice.id ? (
              <li key={notice.id}>
                <NoticeEditor
                  notice={notice}
                  onCancel={() => setEditing(null)}
                  onSaved={() => {
                    setEditing(null);
                    load();
                  }}
                />
              </li>
            ) : (
              <li key={notice.id} className={`notice-item${notice.pinned ? " is-pinned" : ""}`}>
                <button
                  className="notice-title"
                  aria-expanded={open.has(notice.id)}
                  onClick={() => toggle(notice.id)}
                >
                  {notice.pinned ? <span className="badge">고정</span> : null}
                  <strong>{notice.title}</strong>
                  <time>{dateLabel(notice.createdAt)}</time>
                </button>
                {open.has(notice.id) ? (
                  <div className="notice-body">
                    {notice.body ? <NoticeText text={notice.body} /> : null}
                    {isAdmin ? (
                      <div className="notice-admin">
                        {edited(notice) ? <small>고친 때 {dateLabel(notice.updatedAt)}</small> : null}
                        <button onClick={() => setEditing(notice.id)}>고치기</button>
                        <button onClick={() => void remove(notice)}>지우기</button>
                      </div>
                    ) : null}
                  </div>
                ) : null}
              </li>
            ),
          )}
        </ul>
      )}
    </div>
  );
}

function NoticeEditor({
  notice,
  onCancel,
  onSaved,
}: {
  notice?: Notice;
  onCancel: () => void;
  onSaved: (saved: Notice) => void;
}) {
  const [title, setTitle] = useState(notice?.title ?? "");
  const [body, setBody] = useState(notice?.body ?? "");
  const [pinned, setPinned] = useState(notice?.pinned ?? false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  async function save() {
    setSaving(true);
    setError("");
    try {
      const saved = await api<Notice>(notice ? `/api/admin/notices/${notice.id}` : "/api/admin/notices", {
        method: notice ? "PUT" : "POST",
        body: JSON.stringify({ title, body, pinned }),
      });
      onSaved(saved);
    } catch (cause) {
      setError((cause as Error).message);
      setSaving(false);
    }
  }

  return (
    <form
      className="notice-editor"
      onSubmit={(event) => {
        event.preventDefault();
        void save();
      }}
    >
      <input
        value={title}
        onChange={(event) => setTitle(event.target.value)}
        placeholder="제목"
        aria-label="공지 제목"
        maxLength={200}
        autoFocus
      />
      <textarea
        value={body}
        onChange={(event) => setBody(event.target.value)}
        placeholder="본문 — 줄바꿈은 그대로 보이고, 주소는 링크가 됩니다."
        aria-label="공지 본문"
        rows={8}
      />
      <div className="notice-editor-row">
        <label className="notice-pin">
          <input type="checkbox" checked={pinned} onChange={(event) => setPinned(event.target.checked)} />
          맨 위에 고정
        </label>
        <button type="button" onClick={onCancel} disabled={saving}>
          취소
        </button>
        <button type="submit" className="is-primary" disabled={saving || !title.trim()}>
          {saving ? "저장 중…" : notice ? "고친 것 저장" : "올리기"}
        </button>
      </div>
      {error ? <p className="notice is-error">{error}</p> : null}
    </form>
  );
}

/** 본문. 마크다운을 들이지 않고 줄바꿈과 주소만 살린다 — 공지에 그 이상이 필요하면 그때 본다. */
function NoticeText({ text }: { text: string }) {
  const parts: ReactNode[] = [];
  const pattern = /https?:\/\/[^\s<>"')\]]+/g;
  let last = 0;
  for (const match of text.matchAll(pattern)) {
    const at = match.index ?? 0;
    if (at > last) parts.push(text.slice(last, at));
    parts.push(
      <a key={at} href={match[0]} target="_blank" rel="noreferrer">
        {match[0]}
      </a>,
    );
    last = at + match[0].length;
  }
  if (last < text.length) parts.push(text.slice(last));
  return <p className="notice-text">{parts}</p>;
}

/** 올린 뒤 고쳤는가. 올릴 때 두 시각이 몇 ms 갈릴 수 있어서 1분을 넘을 때만 센다. */
function edited(notice: Notice) {
  if (!notice.createdAt || !notice.updatedAt) return false;
  return new Date(notice.updatedAt).getTime() - new Date(notice.createdAt).getTime() > 60_000;
}

function dateLabel(iso: string | null) {
  if (!iso) return "";
  const date = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${date.getFullYear()}.${pad(date.getMonth() + 1)}.${pad(date.getDate())}`;
}
