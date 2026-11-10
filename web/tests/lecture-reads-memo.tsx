// Vite /tests/lecture-reads-memo.html: 서버 없이 강의 패널 통계의 회독 +/지우기/되돌리기와 메모 저장을 확인한다.
import { useState } from "react";
import { createRoot } from "react-dom/client";
import { LectureMemo, ReadEditor } from "../src/calendar/ReadEditor";
import "../src/styles/base.css";
import "../src/styles/calendar.css";

const query = new URLSearchParams(location.search);
let reads = Number(query.get("reads") ?? 0);
const log: string[] = [];
window.fetch = async (input, init) => {
  const path = decodeURIComponent(new URL(String(input), location.origin).pathname);
  const method = init?.method ?? "GET";
  log.push(`${method} ${path}${init?.body ? ` ${init.body}` : ""}`);
  document.querySelector("#log")!.textContent = log.join("\n");
  let payload: object = {};
  if (path.endsWith("/note-reads/last")) payload = { noteReads: reads = Math.max(0, reads - 1) };
  else if (path.endsWith("/note-reads")) payload = { noteReads: ++reads };
  else if (path.endsWith("/my-memo")) payload = { memo: JSON.parse(String(init?.body)).memo.trimEnd() };
  return new Response(JSON.stringify(payload), { status: 200 });
};

function Harness() {
  const [error, setError] = useState("");
  const base = "/api/lectures/감염학/261103_02";
  return <main style={{ maxWidth: 470, padding: 24, margin: "0 auto" }}>
    <section className="panel-stats" aria-label="통계">
      <h3>통계</h3>
      <div className="stat-row">
        <span className="stat-label">회독</span>
        <ReadEditor lecture={{ subject: "감염학", runId: "261103_02" }} base={base} preOpen preDone={query.has("predone")}
          initial={reads} onError={setError} />
      </div>
      <div className="stat-row is-top">
        <span className="stat-label">메모</span>
        <LectureMemo base={base} initial={query.get("memo") ?? ""} onError={setError} />
      </div>
    </section>
    {error ? <p className="notice is-error">{error}</p> : null}
    <pre id="log" />
  </main>;
}

createRoot(document.getElementById("root")!).render(<Harness />);
