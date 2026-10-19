import type { BankFormat } from "../types/bank";

export type QuestionSettings = {
  format: BankFormat; retrieval_direction: string; mcq_mode: "recall_first" | "comparison";
  units: string; choices: string; correctIds: string[]; pairs: string; order: string;
};
export const initialSettings: QuestionSettings = {
  format: "basic", retrieval_direction: "direct", mcq_mode: "recall_first",
  units: "", choices: "", correctIds: [], pairs: "", order: "",
};
const formats: Record<BankFormat, string> = {
  basic: "단답형", cloze: "빈칸", list: "나열", ox: "OX", mcq: "객관식", multi_select: "복수 선택",
  matching: "짝짓기", sequence: "순서",
};
const directions = { direct: "직접 회상", reverse: "역방향 회상", mechanism: "기전",
  discrimination: "구별", integration: "통합", sequence: "순서", trap: "함정" };
const lines = (text: string) => text.split("\n").map(value => value.trim()).filter(Boolean);
const optionId = (index: number) => String(index + 1);

export function settingsPayload(value: QuestionSettings) {
  const choice = value.format === "mcq" || value.format === "multi_select";
  return {
    format: value.format, retrieval_direction: value.retrieval_direction,
    mcq_mode: choice ? value.mcq_mode : "none",
    answer_units: lines(value.units),
    options: choice ? lines(value.choices).map((text, index) => ({ id: optionId(index), text })) : [],
    correct_option_ids: choice ? value.correctIds : [],
    answer_pairs: value.format === "matching" ? lines(value.pairs).map(line => {
      const divider = line.indexOf("|");
      return { left: divider < 0 ? line : line.slice(0, divider).trim(), right: divider < 0 ? "" : line.slice(divider + 1).trim() };
    }) : [],
    correct_order: value.format === "sequence" ? lines(value.order) : [],
  };
}

export function PersonalQuestionSettings({ value, onChange, busy }: {
  value: QuestionSettings; onChange: (value: QuestionSettings) => void; busy: boolean;
}) {
  function field<K extends keyof QuestionSettings>(key: K, next: QuestionSettings[K]) { onChange({ ...value, [key]: next }); }
  const choice = value.format === "mcq" || value.format === "multi_select";
  return <>
    <label>문항 형식<select disabled={busy} value={value.format} onChange={event => onChange({
      ...value, format: event.target.value as BankFormat, correctIds: [],
    })}>{Object.entries(formats).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label>
    <label>회상 방식<select disabled={busy} value={value.retrieval_direction}
      onChange={event => field("retrieval_direction", event.target.value)}>
      {Object.entries(directions).map(([key, label]) => <option key={key} value={key}>{label}</option>)}
    </select></label>
    {value.format === "cloze" ? <small>발문의 빈칸을 {"{{c1}}"}, {"{{c2}}"}로 표시하고, 아래 채점 항목에 빈칸 등장 순서대로 답을 입력하세요.</small> : null}
    {choice ? <>
      <label>객관식 학습 유형<select disabled={busy} value={value.mcq_mode}
        onChange={event => field("mcq_mode", event.target.value as QuestionSettings["mcq_mode"])}>
        <option value="recall_first">기억 확인형 · 먼저 회상 후 선지 공개</option>
        <option value="comparison">구별·판단형 · 선지 바로 공개</option>
      </select></label>
      <label>보기<textarea required disabled={busy} rows={4} maxLength={12000} value={value.choices}
        onChange={event => onChange({ ...value, choices: event.target.value, correctIds: [] })} />
        <small>한 줄에 하나씩, 2개 이상 입력하세요.</small></label>
      <fieldset disabled={busy}><legend>정답 보기{value.format === "mcq" ? " (하나 선택)" : " (모두 선택)"}</legend>
        {lines(value.choices).map((text, index) => {
          const id = optionId(index);
          return <label key={id}><input type={value.format === "mcq" ? "radio" : "checkbox"} name="personal-correct-option"
            checked={value.correctIds.includes(id)} onChange={event => field("correctIds", value.format === "mcq" ? [id]
              : event.target.checked ? [...value.correctIds, id] : value.correctIds.filter(item => item !== id))} />{id}. {text}</label>;
        })}
      </fieldset>
    </> : null}
    {value.format === "matching" ? <label>정답 짝<textarea required disabled={busy} rows={4} maxLength={12000}
      value={value.pairs} placeholder={"용어 | 뜻\n약물 | 작용"} onChange={event => field("pairs", event.target.value)} />
      <small>한 줄에 왼쪽 | 오른쪽 형식으로 2쌍 이상 입력하세요. 풀 때 순서를 섞어 표시합니다.</small></label> : null}
    {value.format === "sequence" ? <label>정답 순서<textarea required disabled={busy} rows={4} maxLength={12000}
      value={value.order} onChange={event => field("order", event.target.value)} />
      <small>한 줄에 한 항목씩 정답 순서로 2개 이상 입력하세요. 풀 때 순서를 섞어 표시합니다.</small></label> : null}
    <label>채점 항목{value.format === "cloze" ? " (빈칸별 정답)" : " (선택)"}<textarea disabled={busy}
      required={value.format === "cloze"} rows={3} maxLength={12000} value={value.units}
      onChange={event => field("units", event.target.value)} /><small>한 줄에 한 항목</small></label>
  </>;
}
