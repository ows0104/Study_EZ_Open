import React, { useState } from "react";
import { createRoot } from "react-dom/client";
import { useBankBuffer, type PreparedFrame } from "../src/bank/useBankBuffer";
import { SlidePreloader } from "../src/slidePreload";

const results: string[] = [];
const check = (yes: unknown, message: string) => { if (!yes) throw new Error(message); results.push(`PASS ${message}`); };
const waitFor = async (test: () => unknown) => {
  for (let i = 0; i < 500; i++) { if (test()) return; await new Promise(r => setTimeout(r, 10)); }
  throw new Error("Timed out");
};
const calls: { body: { lookahead: string }; finish: (frames: Record<string, PreparedFrame>) => void }[] = [];
window.fetch = async (_input, init) => new Promise<Response>(resolve => {
  const body = JSON.parse(String(init!.body));
  calls.push({ body, finish: frames => resolve(new Response(JSON.stringify({ frames, lookahead: body.lookahead }), {
    headers: { "Content-Type": "application/json" },
  })) });
});
const frame = (id: number, next?: number): PreparedFrame => ({
  next: { reviewToken: `t${id}`, question: { question_id: `Q${id}`, question: `QUESTION-${id}` } },
  answer: { answer: `ANSWER-${id}`, slides: [] }, options: {},
  previews: next ? Object.fromEntries(["Again", "Hard", "Good", "Easy"].map(rating => [rating,
    { reviewToken: `t${next}`, question: { question_id: `Q${next}`, question: `QUESTION-${next}` } }])) : {},
} as PreparedFrame);
const slides = new SlidePreloader();
let cache: ReturnType<typeof useBankBuffer>;
let refresh: () => void;
function Harness() {
  const [ack, setAck] = useState(0);
  refresh = () => setAck(value => value + 1);
  cache = useBankBuffer("/api/lectures/test/A/bank", "t1", slides, 0, ack);
  return <p>{cache.size} prepared questions</p>;
}
try {
  createRoot(document.getElementById("root")!).render(<Harness />);
  await waitFor(() => calls.length === 1);
  check(calls[0].body.lookahead === "near", "an empty cache requests the small immediate window first");
  calls[0].finish({ t1: frame(1, 2), t2: frame(2) });
  await waitFor(() => calls.length === 2);
  check(calls[1].body.lookahead === "full", "deep Easy preparation starts in the background");
  check(cache.has("t2") && cache.get("t2")!.answer.answer === "ANSWER-2", "next question and answer are usable while the full request is held");
  check(cache.getFor(frame(1).next)?.answer.answer === "ANSWER-1", "the cached answer matches the visible question");
  check(!cache.getFor({ ...frame(1).next, question: { ...frame(1).next.question!, question_id: "DIFFERENT" } }), "a reused token cannot attach another question's answer");
  const easy = (id: number) => ({ ...frame(id), previews: { Easy: frame(id + 1).next } });
  calls[1].finish({ t1: frame(1, 2), t2: frame(2, 3), t3: easy(3), t4: easy(4), t5: easy(5), t6: easy(6), t7: frame(7) });
  await waitFor(() => cache.has("t3"));
  check(cache.readyEasy("t1", 6), "the Easy path is ready six steps ahead");
  check(!cache.ready("t1", 3), "deep Easy preparation does not require an exponential tree for every rating");
  refresh(); await new Promise(r => setTimeout(r, 50));
  check(calls.length === 2, "a complete window avoids redundant acknowledgement requests");
  document.getElementById("results")!.textContent = results.join("\n") + "\nALL PASSED";
} catch (cause) { document.getElementById("results")!.textContent = results.join("\n") + `\nFAIL ${String(cause)}`; }
