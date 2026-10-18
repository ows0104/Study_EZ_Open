import React, { useState } from "react";
import { createRoot } from "react-dom/client";
import { useBankBuffer, type PreparedFrame } from "../src/bank/useBankBuffer";
import { SlidePreloader } from "../src/slidePreload";

const results: string[] = [];
const check = (yes: unknown, message: string) => {
  if (!yes) throw new Error(message);
  results.push(`PASS ${message}`);
};
const waitFor = async (test: () => unknown) => {
  for (let i = 0; i < 500; i++) {
    if (test()) return;
    await new Promise(resolve => setTimeout(resolve, 10));
  }
  throw new Error("Timed out");
};
const requests: { signal: AbortSignal; token: string; finish: (frames: Record<string, PreparedFrame>) => void }[] = [];
window.fetch = async (_input, init) => new Promise<Response>(resolve => {
  const body = JSON.parse(String(init!.body));
  requests.push({ signal: init!.signal!, token: body.reviewToken,
    finish: frames => resolve(new Response(JSON.stringify({ frames }), {
      headers: { "Content-Type": "application/json" },
    })),
  });
});
const frame = (id: number, successor = false): PreparedFrame => ({
  next: { reviewToken: `token-${id}`, question: { question_id: `Q${id}` } },
  answer: { slides: [] },
  options: {},
  previews: successor ? { Good: { reviewToken: `token-${id + 1}` } } : {},
} as PreparedFrame);
let cache: Map<string, PreparedFrame>;
let update: React.Dispatch<React.SetStateAction<{ token: string; ack: number; revision: number }>>;
const slides = new SlidePreloader();
function Harness() {
  const [state, setState] = useState({ token: "token-1", ack: 0, revision: 0 });
  update = setState;
  cache = useBankBuffer("/api/lectures/test/A/bank", state.token, slides, state.revision, state.ack);
  return <p>{cache.size} frames</p>;
}
try {
  createRoot(document.getElementById("root")!).render(<Harness />);
  await waitFor(() => requests.length === 1);
  requests[0].finish({ "token-1": frame(1, true), "token-2": frame(2, true), "token-3": frame(3) });
  await waitFor(() => cache.has("token-3"));
  update(old => ({ ...old, token: "token-2" }));
  await waitFor(() => requests.length === 2);
  update(old => ({ ...old, token: "token-3", ack: 1 }));
  await waitFor(() => requests.length === 3);
  check(!requests[1].signal.aborted, "rapid navigation and save acknowledgements keep the previous refill running");
  requests[2].finish({ "token-3": frame(3, true), "token-4": frame(4, true), "token-5": frame(5) });
  await waitFor(() => cache.has("token-5"));
  const redrawn = frame(3, true);
  redrawn.previews.Good = { reviewToken: "token-99", selectionTicket: "redrawn-ticket" } as PreparedFrame["next"];
  requests[1].finish({ "token-2": frame(2, true), "token-3": redrawn });
  await new Promise(resolve => setTimeout(resolve, 40));
  check(cache.has("token-5"), "an older reply preserves the deeper prepared window");
  check(cache.get("token-3")?.previews.Good?.reviewToken === "token-4",
    "an older refill cannot redraw an already prepared rating branch");
  update(old => ({ ...old, ack: 2 }));
  await waitFor(() => requests.length === 4);
  cache.clear();
  check(requests[3].signal.aborted, "rollback cancels outstanding preparation");
  requests[3].finish({ "token-99": frame(99) });
  await new Promise(resolve => setTimeout(resolve, 40));
  check(!cache.has("token-99"), "a late reply cannot repopulate a rolled-back buffer");
  update(old => ({ ...old, ack: 3 }));
  await waitFor(() => requests.length === 5);
  update(old => ({ ...old, revision: 1 }));
  await waitFor(() => requests.length === 6);
  check(requests[4].signal.aborted, "editing invalidates outstanding preparation");
  requests[4].finish({ "token-99": frame(99) });
  requests[5].finish({ "token-3": frame(3) });
  await waitFor(() => cache.has("token-3"));
  check(!cache.has("token-99"), "an edited question never reuses stale preparation");
  update(old => ({ ...old, ack: 4 }));
  await waitFor(() => requests.length === 7);
  const allRatings = (id: number) => ({ ...frame(id), previews: Object.fromEntries(
    ["Again", "Hard", "Good", "Easy"].map(rating => [rating, frame(id + 1).next])) });
  requests[6].finish({ "token-3": allRatings(3), "token-4": allRatings(4), "token-5": frame(5) });
  await waitFor(() => cache.has("token-5"));
  update(old => ({ ...old, ack: 5 }));
  await new Promise(resolve => setTimeout(resolve, 40));
  check(requests.length === 7, "save acknowledgements do not refill an already complete two-step window");
  update(old => ({ ...old, token: "token-4" }));
  await waitFor(() => requests.length === 8);
  check(requests[7].token === "token-4", "consuming a step replenishes the window while reading the next question");
  document.getElementById("results")!.textContent = results.join("\n") + "\nALL PASSED";
} catch (error) {
  document.getElementById("results")!.textContent = results.join("\n") + `\nFAIL ${String(error)}`;
}
