export type Mark = '' | 'recalled' | 'partial' | 'learned';
export type Write = { requestId: string; version: number; kind: 'select' | 'map' | 'reveal' | 'rate'; index: number; step?: 'root' | 'follow'; response?: string; marks?: Mark[] };
type Saved = { payload: Write; conflict: boolean };

function decode(raw: string): Write {
  const p = JSON.parse(raw) as Write;
  if (!p || typeof p.requestId !== 'string' || !/^[A-Za-z0-9_-]{1,64}$/.test(p.requestId) || !Number.isInteger(p.version) || p.version < 0
      || !Number.isInteger(p.index) || p.index < 0 || !['select', 'map', 'reveal', 'rate'].includes(p.kind)
      || (p.step !== undefined && p.step !== 'root' && p.step !== 'follow')
      || (p.response !== undefined && typeof p.response !== 'string')
      || (p.marks !== undefined && (!Array.isArray(p.marks) || p.marks.some(m => !['', 'recalled', 'partial', 'learned'].includes(m))))) {
    throw new Error('보관된 요청을 읽을 수 없습니다. 원본은 보존되어 있습니다.');
  }
  return p;
}

export function connectionRecovery(storage: Storage, account: string, subject: string, runId: string, revision: string) {
  const scope = [account, subject, runId, revision];
  const prefix = `studyez:connection-write:v2:${JSON.stringify(scope)}:`;
  const legacy = `studyez:connection-write:${account}:${subject}:${runId}:${revision}`;
  function save(payload: Write, conflict = false) {
    const key = prefix + payload.requestId;
    const old = storage.getItem(key);
    if (old && JSON.stringify(JSON.parse(old).payload) !== JSON.stringify(payload)) {
      throw new Error('보관함에 같은 ID의 다른 요청이 있습니다. 원본을 보존했습니다.');
    }
    storage.setItem(key, JSON.stringify({ payload, conflict }));
  }
  function read() {
    for (const suffix of ['', ':conflict']) {
      const raw = storage.getItem(legacy + suffix);
      if (raw) {
        save(decode(raw), suffix !== '');
        if (storage.getItem(legacy + suffix) === raw) storage.removeItem(legacy + suffix);
      }
    }
    const result: Saved[] = [];
    for (let i = 0; i < storage.length; i++) {
      const key = storage.key(i)!;
      if (!key.startsWith(prefix)) continue;
      const raw = storage.getItem(key);
      if (!raw) continue;
      const entry = JSON.parse(raw) as Saved;
      const payload = decode(JSON.stringify(entry.payload));
      if (typeof entry.conflict !== 'boolean' || key !== prefix + payload.requestId) {
        throw new Error('보관함 형식을 확인하세요. 원본은 보존되어 있습니다.');
      }
      result.push({ payload, conflict: entry.conflict });
    }
    return result;
  }
  const draftKey = (id: string, step: string) => `studyez:connection-draft:v2:${JSON.stringify([...scope, id, step])}`;
  return {
    read, save,
    confirm(payload: Write) {
      const key = prefix + payload.requestId;
      const old = storage.getItem(key);
      if (old && JSON.stringify(JSON.parse(old).payload) === JSON.stringify(payload)) storage.removeItem(key);
    },
    draft: (id: string, step: string) => storage.getItem(draftKey(id, step)) ?? '',
    saveDraft: (id: string, step: string, text: string) => storage.setItem(draftKey(id, step), text),
  };
}
