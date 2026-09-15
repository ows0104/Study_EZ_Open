import { ApiError, api, apiBytes } from "../api";
import { mergeDecks, type MergeReport } from "./apkg";
import type { BundleDeck } from "./decks";

/**
 * 「모아받기」를 누른 뒤에 일어나는 전부 — 받고, 합치고, 저장하고, 받았다고 적는다.
 *
 * **이 파일은 눌러야 내려온다.** 버튼이 `import("./run")` 으로 부르고, 여기가
 * `apkg.ts` 를 통해 sqlite(WASM) 1.5MB 를 끌고 온다. 첫 화면에 실리면 캘린더가
 * 그만큼 늦게 뜬다.
 *
 * 순서가 이 순서인 이유는 하나다 — **받았다고 적는 것이 맨 끝이어야 한다.**
 * 중간에 깨지면(창을 닫거나, 한 편이 404 이거나, 메모리가 모자라거나) 아무것도
 * 안 적히고, 다음에 누르면 그 편들이 그대로 다시 온다. 먼저 적으면 반대가 된다 —
 * 받은 적 없는 덱이 「받은 것」으로 남아 영영 안 온다.
 */

/** 지금 무엇을 하고 있나. 화면이 이것만 보고 줄을 그린다. */
export type BundleProgress = {
  phase: "fetching" | "merging" | "saving";
  /** 몇 편까지 끝났나. `total` 은 담으려는 편 수다. */
  done: number;
  total: number;
  /** 지금 다루는 편. 「만드는 중」만 뜨면 5분째와 40분째가 같은 모양이 된다. */
  label: string;
  /** 지금까지 받은 바이트. 큰 덱이 섞이면 편 수보다 이쪽이 정직하다. */
  bytes: number;
};

export type BundleResult = {
  report: MergeReport;
  /** 담긴 편 수. `decks.length` 와 다를 수 있다 — 아래 `skipped` 만큼. */
  included: number;
  /**
   * 저장소에 없어서 빠진 편.
   *
   * **하나 때문에 스무 편을 막지 않는다.** 화면이 든 목록은 몇 분 전 것이고 그
   * 사이에 「다시 만들기」가 파일을 갈았을 수 있다. 대신 **빠진 것은 이름을 들고
   * 돌아온다** — 조용히 빼면 「12편」이라고 적힌 버튼이 11편을 주고도 아무 말을
   * 안 하게 된다.
   */
  skipped: string[];
};

export async function runBundle(
  decks: BundleDeck[],
  filename: string,
  onProgress: (progress: BundleProgress) => void,
): Promise<BundleResult> {
  if (!decks.length) throw new Error("담을 덱이 없습니다.");

  const included: BundleDeck[] = [];
  const skipped: string[] = [];
  let bytes = 0;

  async function* parts() {
    for (const [index, deck] of decks.entries()) {
      const label = `${deck.title || deck.runId}`;
      onProgress({ phase: "fetching", done: index, total: decks.length, label, bytes });
      const path =
        `/api/bundles/decks/${encodeURIComponent(deck.subject)}` +
        `/${encodeURIComponent(deck.runId)}/${deck.kind}`;
      let payload: Uint8Array;
      try {
        payload = await apiBytes(path);
      } catch (cause) {
        // 없어진 편만 건너뛴다. 401·503 은 **전부에 걸리는 사정**이라 계속 돌면
        // 스무 번 실패하고 빈 파일을 내놓는다.
        if (cause instanceof ApiError && cause.status === 404) {
          skipped.push(label);
          continue;
        }
        throw cause;
      }
      bytes += payload.length;
      included.push(deck);
      onProgress({ phase: "merging", done: index, total: decks.length, label, bytes });
      yield { label, bytes: payload };
    }
  }

  const { blob, report } = await mergeDecks(parts());
  onProgress({ phase: "saving", done: included.length, total: decks.length, label: "", bytes });
  save(blob, `${filename}.apkg`);

  // 파일이 손에 들어간 뒤다. 여기서 실패해도 사람은 덱을 받았으므로 던지지
  // 않는다 — 다음에 누르면 같은 덱이 한 번 더 올 뿐이다.
  try {
    await api("/api/bundles/grabs", {
      method: "POST",
      body: JSON.stringify({
        decks: included.map((deck) => ({ subject: deck.subject, runId: deck.runId, kind: deck.kind })),
      }),
    });
  } catch {
    // 조용히 넘긴다. 버튼이 「받았음」으로 안 바뀌는 것이 증상이고, 다시 누르면 된다.
  }

  return { report, included: included.length, skipped };
}

/**
 * Blob 을 파일로 떨어뜨린다.
 *
 * 주소를 바로 안 버린다 — 누른 순간 브라우저가 아직 Blob 을 읽고 있어서, 곧바로
 * `revokeObjectURL` 을 부르면 200MB 짜리가 중간에 끊긴다. 1분 뒤에 놓는다.
 */
function save(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.rel = "noreferrer";
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
}
