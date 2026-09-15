/**
 * .apkg 여럿을 **한 파일 여러 덱**으로 합친다. 브라우저에서.
 *
 * 하는 일은 `quizgen/bundle.py` 와 같다 — 이미 나온 덱을 열어 노트·덱·미디어를
 * 그대로 옮겨 담는다. **카드를 다시 만들지 않고 guid 도 안 건드린다.** 그래서
 * 이미 임포트한 덱 위에 덮어도 안전하다(같은 노트는 갱신되고 새 노트만 들어간다).
 *
 * 왜 서버가 아니라 여기서 하나 — `server/app/routes/bundles.py` 첫머리에 있다.
 * 요약하면 Cloud Run 이 512Mi 인데 블럭 하나가 200MB 라서다.
 *
 * ## .apkg 안에 무엇이 들었나
 *
 * genanki 0.13 이 내는 것은 zip 하나이고 그 안은 셋뿐이다.
 *
 *     collection.anki2   sqlite (스키마 11). col·notes·cards·revlog·graves
 *     media              {"0": "260831_01_s05.png", "1": …} — 번호 ↔ 진짜 이름
 *     0, 1, 2 …          그림 파일들. 이름이 번호다
 *
 * 덱과 모델은 표가 아니라 `col` 한 줄의 JSON 칸(`decks`·`models`)에 든다. 그래서
 * 합치기는 **그 두 JSON 을 합집합하고 notes·cards 를 옮겨 붓는 일**이 전부다.
 *
 * 덱 id·모델 id 는 이름의 sha256 앞 8바이트라(`quizgen/build.py` 의 `_mid`)
 * **같은 이름이면 어느 편에서 왔든 같은 id 다.** 그래서 합집합이 곧 올바른 병합이고,
 * 편마다 이름이 다른 덱은 저절로 갈라져 선다(`기생충학::[260831_01] …::강의록`).
 *
 * ## 메모리
 *
 * 블럭 하나가 200MB 다. 그래서 둘을 지킨다 —
 *
 *   ① 편 하나를 풀면 **그 자리에서 zip 으로 흘려 보내고 버린다.** 전부 모아 두고
 *     마지막에 압축하면 입력과 출력이 같이 떠서 두 배가 된다.
 *   ② 나온 조각은 편마다 `Blob` 으로 접는다. 브라우저가 큰 Blob 을 디스크로
 *     내리므로 JS 힙이 출력 크기만큼 자라지 않는다.
 *
 * 그림은 이미 PNG·JPEG 라 다시 압축하지 않고 그대로 담는다(`ZipPassThrough`).
 * 압축해 봐야 1~2% 줄고 200MB 를 한 번 더 훑는 값을 치른다.
 */

import { Zip, ZipDeflate, ZipPassThrough, unzip } from "fflate";
import initSqlJs, { type Database, type SqlJsStatic, type SqlValue } from "sql.js";
import wasmUrl from "sql.js/dist/sql-wasm.wasm?url";

/** 담을 덱 하나. `label` 은 실패했을 때 사람에게 보일 이름이다. */
export type DeckPart = { label: string; bytes: Uint8Array };

/** 합친 결과가 실제로 무엇을 들었나. **기대값이 아니라 센 값이다.** */
export type MergeReport = {
  notes: number;
  decks: number;
  media: number;
  /** guid 가 겹쳐 건너뛴 노트. 같은 편을 두 번 담으면 난다. */
  duplicates: number;
  /** 이름이 겹치는데 크기가 다른 그림. 0 이 아니면 어딘가 잘못 구워진 것이다. */
  mediaClashes: number;
};

let sqlPending: Promise<SqlJsStatic> | null = null;

/**
 * sqlite(WASM)를 띄운다. **모아받기를 누른 순간에만 받아 온다.**
 *
 * 1.5MB 짜리라 첫 화면에 실으면 캘린더가 그만큼 늦게 뜬다. 이 파일 전체가
 * `import()` 뒤에 있어서(`bundle/run.ts`) 누르기 전에는 내려오지도 않는다.
 */
function sql(): Promise<SqlJsStatic> {
  if (!sqlPending) {
    sqlPending = initSqlJs({ locateFile: () => wasmUrl }).catch((cause) => {
      // 다음에 누르면 다시 받아 본다. 안 비우면 한 번 실패한 뒤로 영영 막힌다.
      sqlPending = null;
      throw cause;
    });
  }
  return sqlPending;
}

const NOTE_COLUMNS = "id,guid,mid,mod,usn,tags,flds,sfld,csum,flags,data";
const CARD_COLUMNS =
  "id,nid,did,ord,mod,usn,type,queue,due,ivl,factor,reps,lapses,left,odue,odid,flags,data";

/** zip 안에서 collection 이 서는 이름. 새 Anki 는 `.anki21` 도 내므로 둘 다 본다. */
const COLLECTION_NAMES = ["collection.anki21", "collection.anki2"];

/**
 * 덱들을 한 .apkg 로 합친다.
 *
 * `parts` 는 **하나씩 늦게 오는 것**을 받는다(async iterable). 받는 일과 합치는
 * 일이 겹쳐 돌고, 무엇보다 편 하나의 바이트를 다 쓰고 나서 다음 것을 받으므로
 * 스무 편이 동시에 메모리에 뜨지 않는다.
 *
 * `onStep` 은 편 하나를 담을 때마다 불린다 — 화면이 진행을 그린다.
 */
export async function mergeDecks(
  parts: AsyncIterable<DeckPart>,
  onStep?: (label: string, index: number) => void,
): Promise<{ blob: Blob; report: MergeReport }> {
  const SQL = await sql();

  let base: Database | null = null;
  const models: Record<string, unknown> = {};
  const decks: Record<string, unknown> = {};
  const guids = new Set<string>();
  /** 담은 그림. 값은 크기다 — 바이트는 이미 zip 으로 흘려 보내고 안 들고 있다. */
  const mediaSizes = new Map<string, number>();
  const report: MergeReport = { notes: 0, decks: 0, media: 0, duplicates: 0, mediaClashes: 0 };

  // 노트·카드 id 는 Anki 에서 만들어진 시각(ms)이다. 편마다 제 시각을 들고 오므로
  // 그대로 부으면 겹칠 수 있다 — 한 줄로 세워 다시 매긴다. guid 는 안 건드린다.
  let nextId = Date.now();

  let blob: Blob = new Blob([]);
  let chunks: BlobPart[] = [];
  let zipError: Error | null = null;
  let finished!: () => void;
  const done = new Promise<void>((resolve) => {
    finished = resolve;
  });
  const zipper = new Zip((error, chunk, final) => {
    if (error) {
      zipError = error;
      finished();
      return;
    }
    if (chunk.length) chunks.push(chunk);
    if (final) finished();
  });

  /** 지금까지 나온 조각을 Blob 하나로 접는다. 힙에서 디스크로 내리는 일이다. */
  function fold() {
    if (!chunks.length) return;
    blob = new Blob([blob, ...chunks]);
    chunks = [];
  }

  let index = 0;
  try {
    for await (const part of parts) {
      const files = await unzipAsync(part.bytes);
      const name = COLLECTION_NAMES.find((candidate) => files[candidate]);
      if (!name) throw new Error(`${part.label} — 덱 안에 collection 이 없습니다.`);

      const source = new SQL.Database(files[name]);
      try {
        if (base === null) {
          // 첫 편의 것을 **틀로만** 쓴다. 스키마와 `col` 의 기본값(`crt`·`conf`·
          // `dconf`)을 그대로 물려받으려는 것이라 줄은 전부 비운다. 비우지 않으면
          // 첫 편만 제 id 를 들고 남아서 다시 매기는 자리가 둘이 된다.
          base = new SQL.Database(files[name]);
          base.run("DELETE FROM notes; DELETE FROM cards; DELETE FROM revlog; DELETE FROM graves");
        }
        nextId = absorb(source, base, { models, decks, guids, report, nextId });
      } finally {
        source.close();
      }

      // 그림. 이름은 편 ID 로 갈라져 있어서 겹치지 않는 것이 정상이다
      // (`quizgen/build.py` 의 `Media`). 겹치는데 크기까지 다르면 세어서 알린다 —
      // `quizgen/bundle.py` 는 거기서 멈추지만, 여기서 멈추면 사람이 할 수 있는
      // 일이 없다(다시 굽는 것은 러너의 일이다).
      const map = files["media"] ? (JSON.parse(decodeText(files["media"])) as Record<string, string>) : {};
      for (const [blobName, filename] of Object.entries(map)) {
        const bytes = files[blobName];
        if (!bytes) continue;
        const seen = mediaSizes.get(filename);
        if (seen !== undefined) {
          if (seen !== bytes.length) report.mediaClashes += 1;
          continue;
        }
        mediaSizes.set(filename, bytes.length);
        const entry = new ZipPassThrough(String(report.media));
        zipper.add(entry);
        entry.push(bytes, true);
        report.media += 1;
      }

      // 이 편의 바이트는 여기서 할 일이 끝났다. 접어서 힙을 돌려준다.
      fold();
      onStep?.(part.label, index);
      index += 1;
    }

    if (base === null) throw new Error("담을 덱이 하나도 없습니다.");
    report.decks = Object.keys(decks).length;

    base.run("UPDATE col SET models = ?, decks = ?, mod = ?", [
      JSON.stringify(models),
      JSON.stringify(decks),
      Date.now(),
    ]);
    const collection = base.export();
    base.close();

    // 이름 ↔ 번호 표. 순서가 담은 순서와 같아야 하므로 Map 의 삽입 순서를 쓴다.
    const mediaMap: Record<string, string> = {};
    let slot = 0;
    for (const filename of mediaSizes.keys()) mediaMap[String(slot++)] = filename;

    push(zipper, "collection.anki2", collection);
    push(zipper, "media", encodeText(JSON.stringify(mediaMap)));
    zipper.end();
    await done;
    if (zipError) throw zipError;
    fold();
    return { blob: new Blob([blob], { type: "application/octet-stream" }), report };
  } catch (cause) {
    base?.close();
    try {
      zipper.terminate();
    } catch {
      // 이미 끝난 zip 을 끊으면 던진다. 여기서 알릴 것은 원래 오류다.
    }
    throw cause;
  }
}

/** 압축해서 담는다. 텍스트라 줄어든다 — 그림과 달리. */
function push(zipper: Zip, name: string, bytes: Uint8Array) {
  const entry = new ZipDeflate(name, { level: 6 });
  zipper.add(entry);
  entry.push(bytes, true);
}

/**
 * 한 편의 노트·카드·덱·모델을 받는 쪽으로 옮긴다.
 *
 * **덱과 모델은 합집합이면 된다.** id 가 이름의 해시라 같은 이름은 같은 id 이고,
 * 다른 이름은 다른 id 다(`quizgen/build.py` 의 `_mid`). 그래서 덮어써도 같은
 * 값이 덮인다.
 *
 * `Default`(id 1)는 안 옮긴다. 편마다 하나씩 들고 오는 빈 덱이라 옮겨 봐야
 * 받는 쪽이 이미 든 것과 같고, Anki 에서 빈 덱 하나가 더 서는 것도 아니다.
 */
function absorb(
  source: Database,
  base: Database,
  state: {
    models: Record<string, unknown>;
    decks: Record<string, unknown>;
    guids: Set<string>;
    report: MergeReport;
    nextId: number;
  },
): number {
  const [col] = source.exec("SELECT models, decks FROM col");
  if (col) {
    const [modelsJson, decksJson] = col.values[0] as [string, string];
    Object.assign(state.models, JSON.parse(modelsJson));
    for (const [id, deck] of Object.entries(JSON.parse(decksJson) as Record<string, unknown>)) {
      if (id !== "1") state.decks[id] = deck;
    }
  }

  // 한 노트의 카드들. cloze 는 빈칸 수만큼 카드가 서므로 1:1 이 아니다.
  const cardsByNote = new Map<number, SqlValue[][]>();
  for (const row of rows(source, `SELECT ${CARD_COLUMNS} FROM cards`)) {
    const nid = row[1] as number;
    const bucket = cardsByNote.get(nid);
    if (bucket) bucket.push(row);
    else cardsByNote.set(nid, [row]);
  }

  const addNote = base.prepare(`INSERT INTO notes (${NOTE_COLUMNS}) VALUES (${"?,".repeat(10)}?)`);
  const addCard = base.prepare(`INSERT INTO cards (${CARD_COLUMNS}) VALUES (${"?,".repeat(17)}?)`);
  let id = state.nextId;
  try {
    for (const note of rows(source, `SELECT ${NOTE_COLUMNS} FROM notes ORDER BY id`)) {
      const guid = note[1] as string;
      if (state.guids.has(guid)) {
        state.report.duplicates += 1;
        continue;
      }
      state.guids.add(guid);
      const noteId = id++;
      addNote.run([noteId, ...note.slice(1)]);
      for (const card of cardsByNote.get(note[0] as number) ?? []) {
        addCard.run([id++, noteId, ...card.slice(2)]);
      }
      state.report.notes += 1;
    }
  } finally {
    addNote.free();
    addCard.free();
  }
  // 다음 편이 이어 쓸 자리. **받아서 이어 가지 않으면 편마다 같은 수에서 다시
  // 시작해 id 가 겹친다** — sqlite 가 UNIQUE 로 막으므로 조용하지는 않지만,
  // 거기서 멈추면 스무 편이 통째로 안 담긴다.
  return id;
}

/** 한 질의의 모든 줄. `exec` 는 질의가 아무것도 안 주면 빈 배열을 준다. */
function rows(db: Database, query: string): SqlValue[][] {
  const [result] = db.exec(query);
  return result ? result.values : [];
}

/** fflate 의 `unzip` 을 약속으로. 워커에서 풀어서 화면이 안 멈춘다. */
function unzipAsync(bytes: Uint8Array): Promise<Record<string, Uint8Array>> {
  return new Promise((resolve, reject) => {
    unzip(bytes, (error, files) => (error ? reject(error) : resolve(files)));
  });
}

const decoder = new TextDecoder();
const encoder = new TextEncoder();
const decodeText = (bytes: Uint8Array) => decoder.decode(bytes);
const encodeText = (text: string) => encoder.encode(text);
