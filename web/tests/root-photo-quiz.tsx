/**
 * Main-Quiz 사진 문항 화면(2026-11-15 사용자: 「사진이 너무 크고 정렬이 안 되어 있어. 답을 눌러도 답이 바로 안 보여.
 * 힌트도 예습 퀴즈와 같은 버튼 형태로」). 실제 화면 틀 안에서 큰 사진 한 장·두 장을 그려
 * ① 사진이 화면 높이를 다 먹지 않고 카드 가운데에 놓이는지 ② 힌트가 누르기 좋은 알약 버튼인지
 * ③ 답을 열면 답 첫 줄이 스크롤 없이 아래 바 위에 보이는지 잰다. 서버·운영 DB를 부르지 않는다.
 * `?images=4`(2026-11-16 사용자 「사진 배치가 너무 제멋대로」·「정보가 너무 많은듯」): 여러 장은 한 장씩 같은 자리에,
 * A·B·C·D 썸네일과 ←·→로 넘기는지 잰다.
 */
import { createRoot } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";
import "../src/styles/base.css";
import "../src/bank/main-quiz.css";
import type { RootView } from "../src/types/rootLearning";

const results: string[] = [];
const out = () => { document.getElementById("results")!.textContent = results.join("\n"); };
const check = (value: unknown, message: string) => {
  if (!value) throw new Error(message);
  results.push(`PASS ${message}`); out();
};
// 숨은 창에서는 requestAnimationFrame이 멈춘다. 잴 때 배치는 getBoundingClientRect가 바로 계산하므로 시간으로 기다린다.
const frame = () => new Promise(resolve => setTimeout(resolve, 60));
const wait = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));

/** 조직 사진 흉내: 큰 해상도의 무늬 그림. */
function photo(width: number, height: number, hue: number) {
  const c = document.createElement("canvas"); c.width = width; c.height = height;
  const g = c.getContext("2d")!;
  g.fillStyle = `hsl(${hue} 45% 88%)`; g.fillRect(0, 0, width, height);
  for (let i = 0; i < 260; i++) {
    g.fillStyle = `hsl(${hue + (i % 40)} 55% ${45 + (i % 30)}%)`;
    g.beginPath(); g.arc((i * 197) % width, (i * 131) % height, 18 + (i % 5) * 9, 0, Math.PI * 2); g.fill();
  }
  return { sha256: `fake-${width}x${height}-${hue}`, width, height, url: c.toDataURL("image/jpeg", .8), alt: "조직 사진" };
}

const params = new URLSearchParams(location.search);
const images = params.get("images") === "2" ? [photo(1600, 1200, 330), photo(900, 1400, 20)]
  : params.get("images") === "4" ? [photo(1642, 820, 330), photo(946, 1118, 20), photo(310, 300, 200), photo(820, 1640, 120)]
  : [photo(2400, 1800, 330)];
const view = (answered: boolean): RootView => ({
  sessionId: "s1", revision: "v1", version: 1, day: "2026-11-15", policy: {} as RootView["policy"], position: 0, count: 5,
  finished: false, blocked: null, canUndo: true, mapSeen: false, summary: {} as RootView["summary"],
  task: { id: "t1", question: { question_id: "P1", question: "이 사진의 진단명은?", concept_id: "C1", tier: "Core", importance: 5, format: "basic",
    retrieval_direction: "recall", source_refs: [], conflict_id: "", options: [], matching_left: [], matching_right: [], sequence_items: [],
    stimuli: images, clue: "간 · H&E 염색 · 40대 남성, 만성 B형 간염" } as never,
    response: null, attempted: answered ? true : null, helped: false,
    answer: answered ? { answer: "간세포암(Hepatocellular carcinoma)", answerUnits: ["간세포암(Hepatocellular carcinoma)"], answerPairs: [],
      correctOrder: [], correctOptionIds: [], medicalReview: null, slides: [] } as never : null },
});

try {
  const { RootSolve } = await import("../src/bank/RootSolve");
  const root = createRoot(document.getElementById("root")!);
  let answered = false;
  const render = () => root.render(<MemoryRouter><main className="root-learning main-quiz-learning">
    <RootSolve view={view(answered)} scope="photo" disabled={false} advancing={false}
      onAction={action => { if (action.kind === "reveal") { answered = true; render(); } }} onToday={() => {}} onError={() => {}} />
  </main></MemoryRouter>);
  try { localStorage.setItem("studyez:quiz-timer", "off"); } catch { /* 저장소 없이도 돈다 */ }
  render();
  const imgs = () => [...document.querySelectorAll<HTMLImageElement>(".mq-card .bank-stimuli img")];
  for (let i = 0; i < 50 && !imgs().every(img => img.complete && img.naturalWidth); i++) await wait(50);
  await frame(); scrollTo(0, 0); await frame();
  /** 화면에 보이는 문항 사진(썸네일·숨긴 장 제외). */
  const shown = () => imgs().filter(img => !img.closest(".stimulus-strip") && img.getBoundingClientRect().height > 0);
  check(!document.querySelector<HTMLButtonElement>(".quiz-submit")!.disabled, "answer button opens once every photo has loaded (hidden ones too)");

  if (images.length > 2) {
    const stage = () => document.querySelector(".mq-card .stimulus-stage")!.getBoundingClientRect();
    const label = () => document.querySelector(".mq-card .stimulus-stage figure:not([hidden]) .stimulus-label")?.textContent;
    const thumbs = [...document.querySelectorAll<HTMLButtonElement>(".mq-card .stimulus-strip button")];
    check(shown().length === 1 && label() === "A", `one photo at a time, labelled A (shown ${shown().length}, label ${label()})`);
    check(thumbs.map(b => b.textContent).join("") === "ABCD" && thumbs[0].getAttribute("aria-pressed") === "true", "thumbnails A–D under the photo, A current");
    const height = stage().height, top = document.querySelector(".mq-card .stimulus-strip")!.getBoundingClientRect().top;
    window.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowRight", bubbles: true })); await frame();
    check(label() === "B" && thumbs[1].getAttribute("aria-pressed") === "true", "→ moves to B");
    thumbs[3].click(); await frame();
    check(label() === "D" && shown().length === 1, "clicking thumbnail D shows D");
    check(Math.abs(stage().height - height) < 1 && Math.abs(document.querySelector(".mq-card .stimulus-strip")!.getBoundingClientRect().top - top) < 1,
      "switching photos does not move the thumbnails (fixed stage)");
    window.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowRight", bubbles: true })); await frame();
    check(label() === "A", "→ after the last photo wraps to A");
    const lr = document.querySelector(".mq-card .stimulus-stage figure:not([hidden]) .stimulus-label")!.getBoundingClientRect();
    const pr = shown()[0].getBoundingClientRect();
    check(lr.left >= pr.left && lr.top >= pr.top && lr.right <= pr.right, "the letter sits on the photo's own corner");
  }

  const card = document.querySelector(".mq-card")!.getBoundingClientRect();
  const box = document.querySelector(".mq-card .bank-stimuli")!.getBoundingClientRect();
  for (const img of shown()) {
    const r = img.getBoundingClientRect();
    check(r.height <= innerHeight * 0.56 + 1, `photo before answer is at most ~55% of the screen (got ${Math.round(r.height)} of ${innerHeight})`);
    check(Math.abs(r.width / r.height - img.naturalWidth / img.naturalHeight) < 0.02, "photo keeps its aspect ratio");
  }
  const left = Math.min(...shown().map(i => i.getBoundingClientRect().left)), right = Math.max(...shown().map(i => i.getBoundingClientRect().right));
  check(Math.abs((left + right) / 2 - (card.left + card.right) / 2) <= 2, `photos sit in the middle of the card (photos ${Math.round(left)}–${Math.round(right)}, card ${Math.round(card.left)}–${Math.round(card.right)})`);
  check(box.right <= card.right + 1, "photos stay inside the card");

  const hint = document.querySelector<HTMLButtonElement>(".mq-clue .quiz-hint-toggle");
  check(hint, "hint is the pre-quiz style pill button");
  const hr = hint!.getBoundingClientRect();
  check(hr.height >= 40 && hr.width >= 120, `hint button is easy to press (${Math.round(hr.width)}×${Math.round(hr.height)})`);
  check(getComputedStyle(hint!).borderRadius.startsWith("999") || parseFloat(getComputedStyle(hint!).borderRadius) >= hr.height / 2, "hint button is rounded like the pre-quiz hint");
  check(hint!.getAttribute("aria-expanded") === "false" && !document.querySelector(".mq-clue > p"), "hint starts closed");
  hint!.click(); await frame();
  check(hint!.getAttribute("aria-expanded") === "true" && document.querySelector(".mq-clue > p")?.textContent?.includes("H&E"), "clicking opens the hint");
  document.querySelector<HTMLElement>(".main-quiz-question-heading")!.dispatchEvent(new KeyboardEvent("keydown", { key: "h", code: "KeyH", bubbles: true }));
  await frame();
  check(hint!.getAttribute("aria-expanded") === "false", "H closes the hint again");
  // ?stay=1: 답 전 화면을 눈으로 볼 때. 힌트를 펴 둔 채 멈춘다.
  if (params.get("stay")) { hint!.click(); throw "stopped before the answer (?stay=1)"; }

  document.querySelector<HTMLButtonElement>(".quiz-submit")!.click();
  for (let i = 0; i < 20 && !document.querySelector(".mq-card .quiz-line"); i++) await frame();
  await frame();
  check(scrollY === 0, `revealing does not jump the page (scrollY ${scrollY})`);
  const bar = document.querySelector(".main-quiz-solve .quiz-bar")!.getBoundingClientRect();
  const answerLine = document.querySelector(".mq-card .quiz-line")!.getBoundingClientRect();
  const answerText = document.querySelector(".mq-card .quiz-line ~ *")!.getBoundingClientRect();
  check(answerLine.top < bar.top && answerText.top + 24 < bar.top,
    `answer is visible above the bottom bar without scrolling (answer top ${Math.round(answerText.top)}, bar top ${Math.round(bar.top)})`);
  results.push("ALL PASSED"); out();
} catch (error) { results.push(`FAIL ${String(error)}`); out(); }
