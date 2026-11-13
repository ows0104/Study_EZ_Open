/**
 * 자유 노트 사진은 이 브라우저(IndexedDB)에만 둔다(2026-11-13 사용자 지시: 서버 용량 때문에 사진은 올리지 않는다).
 * 서버 노트에는 사진 id만 들어간다. 다른 기기·브라우저, 사이트 데이터를 지운 뒤에는 사진이 없다.
 * 같은 브라우저를 여러 계정이 쓸 수 있어 계정 id(userId)로 나눈다.
 */

const DB_NAME = 'studyez-note-images';
const STORE = 'images';
const MAX_SIDE = 1600;
const QUALITY = 0.85;

export type LocalImage = { id: string; userId: string; noteId: string; blob: Blob; w: number; h: number; createdAt: number };

let opening: Promise<IDBDatabase> | null = null;

function open(): Promise<IDBDatabase> {
  if (!opening) {
    opening = new Promise<IDBDatabase>((resolve, reject) => {
      if (typeof indexedDB === 'undefined') {
        reject(new Error('이 브라우저는 사진 저장을 지원하지 않습니다.'));
        return;
      }
      const req = indexedDB.open(DB_NAME, 1);
      req.onupgradeneeded = () => {
        const store = req.result.createObjectStore(STORE, { keyPath: 'id' });
        store.createIndex('noteId', 'noteId');
      };
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(req.error ?? new Error('사진 저장소를 열 수 없습니다.'));
    });
    opening.catch(() => {
      opening = null;
    });
  }
  return opening;
}

function run<T>(mode: IDBTransactionMode, fn: (store: IDBObjectStore) => IDBRequest<T> | void): Promise<T | undefined> {
  return open().then((db) => new Promise<T | undefined>((resolve, reject) => {
    const tx = db.transaction(STORE, mode);
    const req = fn(tx.objectStore(STORE));
    tx.oncomplete = () => resolve(req ? req.result : undefined);
    tx.onerror = () => reject(tx.error ?? new Error('사진 저장에 실패했습니다.'));
    tx.onabort = () => reject(tx.error ?? new Error('사진 저장에 실패했습니다.'));
  }));
}

/** 서버 계약(`^[a-z0-9]{8,40}$`)에 맞는 id. */
export function newImageId(): string {
  const bytes = crypto.getRandomValues(new Uint8Array(12));
  return Array.from(bytes, (b) => b.toString(36).padStart(2, '0')).join('').slice(0, 20);
}

/** 긴 변 1600px로 줄여 다시 담는다(EXIF 등 원본 정보도 이때 빠진다). WebP가 안 되면 JPEG. */
async function shrink(file: Blob): Promise<{ blob: Blob; w: number; h: number }> {
  const bitmap = await createImageBitmap(file);
  const scale = Math.min(1, MAX_SIDE / Math.max(bitmap.width, bitmap.height));
  const w = Math.max(1, Math.round(bitmap.width * scale));
  const h = Math.max(1, Math.round(bitmap.height * scale));
  const canvas = document.createElement('canvas');
  canvas.width = w;
  canvas.height = h;
  canvas.getContext('2d')!.drawImage(bitmap, 0, 0, w, h);
  bitmap.close();
  const encode = (type: string) => new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, type, QUALITY));
  let blob = await encode('image/webp');
  if (!blob || blob.type !== 'image/webp') blob = await encode('image/jpeg');
  if (!blob) throw new Error('사진을 읽을 수 없습니다.');
  return { blob, w, h };
}

export async function saveImage(file: Blob, userId: string, noteId: string): Promise<string> {
  const { blob, w, h } = await shrink(file);
  const id = newImageId();
  const record: LocalImage = { id, userId, noteId, blob, w, h, createdAt: Date.now() };
  await run('readwrite', (s) => s.put(record));
  return id;
}

export async function readImage(id: string, userId: string): Promise<LocalImage | null> {
  const found = await run<LocalImage>('readonly', (s) => s.get(id));
  return found && found.userId === userId ? found : null;
}

/** 노트를 지울 때 이 기기에 있는 그 노트의 사진도 지운다(다른 기기의 사진은 지울 수 없다). */
export async function deleteNoteImages(noteId: string, userId: string): Promise<void> {
  await run('readwrite', (s) => {
    const req = s.index('noteId').openCursor(IDBKeyRange.only(noteId));
    req.onsuccess = () => {
      const cursor = req.result;
      if (!cursor) return;
      if ((cursor.value as LocalImage).userId === userId) cursor.delete();
      cursor.continue();
    };
  });
}

export const imageFiles = (data: DataTransfer | null): File[] =>
  data ? Array.from(data.files).filter((f) => f.type.startsWith('image/')) : [];
