import { createRoot } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";
import { RootGenerationPanel } from "../src/bank/RootGenerationPanel";

const results: string[] = [];
const check = (yes: unknown, message: string) => { if (!yes) throw new Error(message); results.push(`PASS ${message}`); };
const wait = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));

const generation = {
  id: "a".repeat(32), requestId: "req", jobId: 1, state: "running", stage: "출제", message: "진행 중",
  published: false, revision: "r1", privatePilot: true, featureEnabled: true,
  input: { conceptMap: "map", points: "points", scope: "scope", examDate: null, inputMode: "source" },
  report: null, authoring: "web", awaitingWeb: false, dispatched: false,
};

const calls: { url: string; finish: () => void }[] = [];
window.fetch = async (input) => new Promise<Response>(resolve => {
  calls.push({ url: String(input), finish: () => resolve(new Response(JSON.stringify({ generation }), {
    headers: { "Content-Type": "application/json" },
  })) });
});

const polls = () => calls.filter(call => call.url.includes("/generation"));

async function run() {
  createRoot(document.getElementById("root")!).render(
    <MemoryRouter><RootGenerationPanel subject="test" runId="demo"/></MemoryRouter>);
  // 화면이 열릴 때의 첫 읽기.
  await wait(500);
  check(polls().length === 1, "화면이 열리면 기존 작업을 한 번 읽는다");
  polls()[0].finish();
  await wait(500);
  check(document.body.textContent!.includes("생성·업로드 진행 중"), "진행 중 작업을 표시한다");

  // 첫 폴링은 3초 뒤에 나간다. 그 응답을 쥐고 있는 동안에는 다음 것이 나가지 않는다.
  await wait(3600);
  check(polls().length === 2, "3초 뒤 폴링이 한 번 나간다");
  await wait(4000);
  check(polls().length === 2, "앞 응답을 기다리는 동안 폴링이 겹쳐 쌓이지 않는다");

  // 응답이 돌아오면 다시 3초를 센다.
  polls()[1].finish();
  await wait(3600);
  check(polls().length === 3, "응답이 돌아온 뒤 다음 폴링을 센다");
  polls()[2].finish();
}

run().then(() => { results.push("ALL PASSED"); })
  .catch((error: Error) => { results.push(`FAIL ${error.message}`); })
  .finally(() => { document.getElementById("results")!.textContent = results.join("\n"); });
