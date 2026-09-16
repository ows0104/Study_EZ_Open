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
  /* 덱이 하나도 없어도 **자리는 남긴다**(2026-09-16 관리자 지시 — 없어도
     비활성화 버튼으로 자리만 놔줘). 저장소가 원래 그렇게 한다 — 덱 칸도
     「아직 없습니다」로 서고(`DeckSlot` 의 `DeckAction`), 칸의 점도 빈 자리를
     그린다. 빠지면 **도형이 생기고 사라지는 대로 옆 칸과 줄이 안 맞고**, 무엇보다
     「아직 안 구웠다」와 「이 날은 원래 없다」가 같은 빈칸이 된다.

     눌리지는 않는다. 받을 것이 없는데 버튼이 살아 있으면 눌러 보고 나서야 안다. */
  const empty = count.total === 0;

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
  const head = compact || empty ? what : headline(what, count.fresh, count.total);
  // **크기는 따로 싼다.** 칸이 좁아지면 이것부터 접는다(`@container foot`) —
  // 잘려서 「4편 · 11…」이 되느니 「4편」이 온전한 편이 낫다. 접힌 값은 `title`
  // 이 든다.
  const [rest, size] = busy
    ? [running(progress!, compact), ""]
    : detail(count.fresh, count.total, count.freshBytes, compact);
  const spoken = `${what} 모아받기 — ${rest}${size ? ` · ${size}` : ""}`;

  return (
    <div className={`bundle is-${kind}${compact ? " is-compact" : ""}`}>
      <button
        className={`bundle-hit${empty ? " is-none" : count.fresh ? "" : " is-spent"}`}
        onClick={() => void start()}
        disabled={busy || empty}
        aria-busy={busy}
        aria-label={spoken}
        title={
          empty
            ? `${what} 덱이 아직 없습니다. 만들어지면 여기서 한 파일로 받습니다.`
            : error
              ? `${what} 모아받기 — ${error}`
              : `${spoken} — ${hint(count.total, count.fresh)}`
        }
      >
        <strong>{head}</strong>
        <small>
          {rest}
          {size ? <b className="bundle-size"> · {size}</b> : null}
        </small>
      </button>
      {/* 무엇이 실제로 담겼는지. **버튼이 약속한 수가 아니라 센 수다** — 다시
          굽는 중에 갈린 편은 빠지고, 그때 아무 말이 없으면 12편이라고 적힌
          버튼이 11편을 주고도 조용하다.

          **좁은 쪽에서는 어긋났을 때만 적는다.** 예습·복습이 좌우로 서면서 칸이
          반이 됐고, 거기에 성공 줄까지 깔면 네 줄로 접혀 격자 아랫줄이 부푼다.
          잘 끝난 것은 버튼이 「다 받음」으로 바뀌는 것이 이미 말한다 — 이 줄이
          혼자 할 수 있는 말은 **약속과 다르다**는 것뿐이다. */}
      {result && (!compact || result.skipped.length || result.report.duplicates) ? (
        <p className="bundle-note">{landed(result, compact)}</p>
      ) : null}
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
 *
 * 좁은 쪽은 말을 줄인다. 예습·복습이 한 줄에 좌우로 서면서 칸 폭이 반이 됐고
 * (2026-09-16 관리자 지시), 제일 좁을 때 글이 들어갈 자리가 50px 남짓이다.
 * 「새로 나온 2편」이 `+2편` 이 된 것이 그래서다 — 뜻은 `title` 이 온전히 든다.
 */
function detail(
  fresh: number,
  total: number,
  bytes: number,
  compact: boolean,
): [main: string, size: string] {
  if (!total) return [compact ? "없음" : "아직 없습니다", ""];
  if (!fresh) return [compact ? "다 받음" : `${total}편 다시 받기`, ""];
  if (compact) return [`${fresh < total ? `+${fresh}` : total}편`, shortSize(bytes)];
  return ["한 파일로 받기", fileSize(bytes)];
}

/**
 * 좁은 네모에 드는 크기. **10MB 를 넘으면 소수점을 뗀다** — `112.8MB` 는 여섯
 * 글자이고 `113MB` 는 다섯이다. 한 자리 차이가 잘리느냐 마느냐를 가른다.
 */
function shortSize(bytes: number): string {
  const mb = bytes / 1024 / 1024;
  if (mb < 1) return `${Math.max(1, Math.round(bytes / 1024))}KB`;
  return mb >= 10 ? `${Math.round(mb)}MB` : `${mb.toFixed(1)}MB`;
}

/** 무엇이 일어나는지. **갈래 이름은 안 붙인다** — `spoken` 이 이미 달고 있다. */
function hint(total: number, fresh: number): string {
  return fresh
    ? `안 받은 ${fresh}편을 한 파일에 담습니다. 덱은 편마다 갈라져 들어갑니다.`
    : `${total}편을 다시 한 파일에 담습니다. 이미 받은 것이라 Anki 에서는 갱신만 됩니다.`;
}

/** 한 마디로 무엇을 하고 있나. **「만드는 중」만 뜨면 1편째와 20편째가 같다.** */
function running(progress: BundleProgress, compact: boolean): string {
  if (progress.phase === "saving") return compact ? "저장 중…" : "저장하는 중…";
  const place = `${Math.min(progress.done + 1, progress.total)}/${progress.total}`;
  const doing = progress.phase === "fetching" ? "받는 중" : "담는 중";
  // 좁은 쪽에는 크기까지 안 넣는다. 몇 편째인지가 먼저 잘리면 안 된다.
  if (compact) return `${doing} ${place}`;
  return `${doing} ${place}` + (progress.bytes ? ` · ${fileSize(progress.bytes)}` : "");
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
