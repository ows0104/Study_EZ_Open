// Main-Quiz 「문제 수정·제보」 형식 바꾸기(2026-11-17, docs/changes/2026-11-17-personal-edit-format).
// 가짜 API로 수정창만 띄운다. 서버·운영 DB를 부르지 않는다.
import { createRoot } from "react-dom/client";
import "../src/styles/base.css";
import { PersonalQuestionDialog } from "../src/bank/PersonalQuestionDialog";

const results: string[] = [];
const check = (ok: unknown, message: string) => {
  if (!ok) throw new Error(message);
  results.push(`PASS ${message}`);
  document.getElementById("results")!.textContent = results.join("\n");
};
const waitFor = async (test: () => unknown) => {
  for (let i = 0; i < 500; i++) { if (test()) return; await new Promise(resolve => setTimeout(resolve, 10)); }
  throw new Error("Timed out");
};
const PATH = "/api/root-learning/lectures/test/demo/questions/Q1/personal";
const original = { question: "Mucor의 균사 격막은?", answer: "격막이 없거나 드묾", explanation: "원래 해설", format: "basic",
  mcqMode: "none", options: [], correctOptionIds: [] };
const puts: Record<string, unknown>[] = [];
window.fetch = async (input, init) => {
  const path = new URL(String(input), location.origin).pathname;
  if (path !== PATH) throw new Error(`Unexpected request: ${path}`);
  if (init?.method === "PUT") {
    puts.push(JSON.parse(String(init.body)));
    return new Response(JSON.stringify({ question: { question_id: "Q1" }, answer: {}, reported: true }), { headers: { "Content-Type": "application/json" } });
  }
  return new Response(JSON.stringify({ original, draft: original, edited: false, revision: "r".repeat(64), comment: "",
    personalAdded: false, editable: true, formats: ["basic", "list", "cloze", "ox", "mcq", "multi_select"] }),
  { headers: { "Content-Type": "application/json" } });
};
const set = (element: HTMLTextAreaElement | HTMLSelectElement, value: string) => {
  Object.getOwnPropertyDescriptor(Object.getPrototypeOf(element), "value")!.set!.call(element, value);
  element.dispatchEvent(new Event(element instanceof HTMLSelectElement ? "change" : "input", { bubbles: true }));
};
const q = <T extends Element>(selector: string) => document.querySelector<T>(selector);
const labelled = (text: string) => [...document.querySelectorAll("dialog label")].find(label => label.textContent?.startsWith(text));
const field = (text: string) => labelled(text)?.querySelector<HTMLTextAreaElement>("textarea") ?? null;
const submit = async () => { const before = puts.length; q<HTMLButtonElement>("dialog button[type=submit]")!.click(); await waitFor(() => puts.length > before); return puts.at(-1)!; };

createRoot(document.getElementById("root")!).render(
  <PersonalQuestionDialog path={PATH} questionId="Q1" answerVisible={false} onClose={() => {}} onSaved={() => {}} />);

(async () => {
  await waitFor(() => q("dialog select"));
  const select = q<HTMLSelectElement>("dialog select")!;
  check([...select.options].map(o => o.textContent).join("|") === "주관식 (원래 형식)|나열|빈칸|OX|객관식|복수 선택", "offers the six Main-Quiz formats");

  set(select, "cloze");
  await waitFor(() => document.body.textContent?.includes("중괄호로 감싸세요"));
  check(!field("정답"), "cloze needs no separate answer box");
  check(field("해설")?.value === "원래 해설", "explanation starts from the original");
  set(field("발문")!, "Mucor의 균사 격막은 {없거나 드묾}");
  let body = await submit();
  check(body.answer === "" && JSON.stringify(body.structure) === JSON.stringify({ format: "cloze", mcq_mode: "none", explanation: "원래 해설", options: [], correct_option_ids: [] }),
    "saves cloze as a structure with the stem's blanks");

  set(select, "mcq");
  await waitFor(() => labelled("보기"));
  check(field("발문")!.value === "Mucor의 균사 격막은 없거나 드묾", "leaving cloze strips the braces only");
  check(field("보기")!.value === "격막이 없거나 드묾" && q<HTMLInputElement>("input[name=personal-correct-option]")!.checked,
    "the current answer becomes the first, correct choice");
  set(field("보기")!, "격막이 없거나 드묾\n격막이 뚜렷함");
  check(document.querySelectorAll("input[name=personal-correct-option]:checked").length === 0, "editing choices clears the correct pick");
  (document.querySelectorAll<HTMLInputElement>("input[name=personal-correct-option]")[0]).click();
  body = await submit();
  const structure = body.structure as { format: string; mcq_mode: string; options: { id: string; text: string }[]; correct_option_ids: string[] };
  check(structure.format === "mcq" && structure.mcq_mode === "comparison" && structure.options.length === 2
    && structure.correct_option_ids.join() === "1", "saves mcq with numbered choices and its correct id");

  set(select, "ox");
  await waitFor(() => q("input[name=personal-ox]"));
  check(document.querySelectorAll("input[name=personal-ox]:checked").length === 0, "OX starts unpicked when the answer is not O/X");
  document.querySelectorAll<HTMLInputElement>("input[name=personal-ox]")[1].click();
  body = await submit();
  check(body.answer === "X" && (body.structure as { format: string }).format === "ox", "saves OX with the picked mark");

  set(select, "basic");
  await waitFor(() => document.body.textContent?.includes("정답 확인·수정"));
  body = await submit();
  check(!("structure" in body), "the original format saves text only, as before");
  document.title = "PASS";
})().catch(error => { document.getElementById("results")!.textContent = `FAIL ${error.message}\n${results.join("\n")}`; document.title = "FAIL"; });
