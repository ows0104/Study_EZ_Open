import { useState } from "react";
import { fileSize } from "../calendar/panelShared";
import type { DeckKind } from "../types";
import { bundleName, tally, type BundleDeck, type BundleScope } from "./decks";
import type { BundleProgress, BundleResult } from "./run";

/**
 * 「한 파일로 모아받기」 버튼 하나. 하루치이거나 블럭(과목) 전체다.
 *
 * **버튼이 상태를 말한다.** 셋으로 갈린다 —
 *
 *     아직 하나도 안 받음     「예습 12편 · 84MB」
 *     받고 나서 새 편이 생김   「예습 새로 나온 3편 · 21MB」   ← 눌리면 그 셋만 담는다
 *     다 받음                 「예습 다 받았습니다 · 12편 다시 받기」
 *
 * 가운데 줄이 이 기능의 요점이다(2026-09-15 관리자 지시). 블럭 하나가 200MB 라
 * 「전체 받기」를 매번 누르면 스무 편을 다시 받는데, 그중 새것은 보통 한둘이다.
 * 무엇을 받아 갔는지는 서버가 이미 알고 있다 — `asset_grab` 표이고, 덱 한 편을
 * 받을 때마다 쌓여 왔다.
 *
 * **「다 받았습니다」를 눌리게 둔다.** 기계를 바꿨거나 Anki 를 지운 사람이 있고,
 * 그 사람에게 「다 받았습니다」만 적힌 죽은 칸을 주면 할 수 있는 일이 없다.
 *
 * `compact` 는 **캘린더 맨 아랫줄**이다(2026-09-16 관리자 지시 — 날짜 머리에
 * 알약으로 붙였더니 안 예쁘다, 시간표 제일 아래에 네모로 넣어라). 좁아서 꼴이
 * 다른 것이 아니라 **자리가 다른 것이라** 생김새를 칸의 딱지(`.calendar-event`)에
 * 맞춘다 — 같은 열에 서는 것끼리 같은 네모여야 한다. 드는 말은 두 자리가 같다.
 *
 * 무거운 것(sqlite WASM · 합치는 코드)은 **누른 뒤에** 내려온다 — `import("./run")`.
 */
export function BundleButton({
  scope,
  kind,
  decks,
  compact = false,
  onDone,
}: {
  scope: BundleScope;
  kind: DeckKind;
  /** 이 범위 · 이 갈래의 덱 전부. 고르는 것은 여기서 한다. */
  decks: BundleDeck[];
  /** 캘린더 맨 아랫줄인가. 칸의 딱지와 같은 네모로 선다. */
  compact?: boolean;
  /** 끝나면 목록을 다시 읽는다 — 안 그러면 버튼이 옛 수를 든 채로 남는다. */
  onDone: () => void;
}) {
  const [progress, setProgress] = useState<BundleProgress | null>(null);
  const [result, setResult] = useState<BundleResult | null>(null);
  const [error, setError] = useState("");

  const what = kind === "pre" ? "예습" : "복습";
  const count = tally(decks);
  // 덱이 하나도 없는 날·과목에는 자리를 안 만든다. 「0편」이 서 있으면 아직 안
  // 구운 것과 원래 없는 것이 같은 모양이 된다 — 그 구분은 칸의 점이 한다.
  if (!count.total) return null;

  const onlyFresh = count.fresh > 0;
  const target = onlyFresh ? decks.filter((deck) => !deck.grabbed) : decks;
  const busy = progress !== null;

  async function start() {
    setError("");
    setResult(null);
    setProgress({ phase: "fetching", done: 0, total: target.length, label: "", bytes: 0 });
    try {
      const { runBundle } = await import("./run");
      const answer = await runBundle(target, bundleName(scope, kind, onlyFresh), setProgress);
      setResult(answer);
      onDone();
    } catch (cause) {
      setError((cause as Error).message);
    } finally {
      setProgress(null);
    }
  }

  // 좁은 자리에서는 윗줄이 갈래 이름뿐이다. 수와 크기는 아랫줄이 통째로 맡는다.
  const head = compact ? what : headline(what, count.fresh, count.total);
  const rest = busy ? running(progress!) : detail(count.fresh, count.total, count.freshBytes, compact);

  return (
    <div className={`bundle is-${kind}${compact ? " is-compact" : ""}`}>
      <button
        className={`bundle-hit${count.fresh ? "" : " is-spent"}`}
        onClick={() => void start()}
        disabled={busy}
        aria-busy={busy}
        aria-label={`${what} 모아받기 — ${rest}`}
        title={error ? `${what} 모아받기 — ${error}` : hint(what, count.total, count.fresh)}
      >
        <strong>{head}</strong>
        <small>{rest}</small>
      </button>
      {/* 무엇이 실제로 담겼는지. **버튼이 약속한 수가 아니라 센 수다** — 다시
          굽는 중에 갈린 편은 빠지고, 그때 아무 말이 없으면 12편이라고 적힌
          버튼이 11편을 주고도 조용하다. */}
      {result ? <p className="bundle-note">{landed(result, compact)}</p> : null}
      {/* 실패도 자리에 남긴다. 좁은 칸이라고 접으면 「눌렀는데 아무 일도
          없었다」가 된다 — 사유는 `title` 에도 같이 든다. */}
      {error ? <p className="bundle-note is-error">{error}</p> : null}
    </div>
  );
}

/** 넓은 자리의 윗줄. */
function headline(what: string, fresh: number, total: number): string {
  if (!fresh) return `${what} 다 받았습니다`;
  if (fresh < total) return `${what} 새로 나온 ${fresh}편`;
  return `${what} ${total}편`;
}

/**
 * 아랫줄. **좁은 자리에서는 이 줄 하나가 「몇 편이 · 얼마나」를 다 말한다** —
 * 윗줄에 갈래 이름밖에 안 서므로, 여기가 비면 버튼이 아무것도 안 말하게 된다.
 */
function detail(fresh: number, total: number, bytes: number, compact: boolean): string {
  if (!fresh) return compact ? `다 받았습니다 · ${total}편 다시` : `${total}편 다시 받기`;
  const head = fresh < total ? `새로 나온 ${fresh}편` : `${total}편`;
  return compact ? `${head} · ${fileSize(bytes)}` : `한 파일로 받기 · ${fileSize(bytes)}`;
}

function hint(what: string, total: number, fresh: number): string {
  const tail = fresh
    ? `안 받은 ${fresh}편을 한 파일에 담습니다. 덱은 편마다 갈라져 들어갑니다.`
    : `${total}편을 다시 한 파일에 담습니다. 이미 받은 것이라 Anki 에서는 갱신만 됩니다.`;
  return `${what} 모아받기 — ${tail}`;
}

/** 한 마디로 무엇을 하고 있나. **「만드는 중」만 뜨면 1편째와 20편째가 같다.** */
function running(progress: BundleProgress): string {
  if (progress.phase === "saving") return "저장하는 중…";
  const place = `${Math.min(progress.done + 1, progress.total)}/${progress.total}`;
  const size = progress.bytes ? ` · ${fileSize(progress.bytes)}` : "";
  return (progress.phase === "fetching" ? `받는 중 ${place}` : `담는 중 ${place}`) + size;
}

function landed(result: BundleResult, compact: boolean): string {
  const parts = [`${result.included}편`, `카드 ${result.report.notes}장`];
  if (!compact) parts.push(`덱 ${result.report.decks}개`);
  if (result.skipped.length) {
    // 빠진 것은 이름을 들고 나온다. 좁은 칸에는 이름이 안 들어가므로 수만.
    parts.push(
      compact
        ? `빠짐 ${result.skipped.length}편`
        : `빠짐 ${result.skipped.length}편 — ${result.skipped.join(", ")}`,
    );
  }
  if (result.report.duplicates) parts.push(`겹쳐서 접음 ${result.report.duplicates}장`);
  return `받았습니다 — ${parts.join(" · ")}`;
}
