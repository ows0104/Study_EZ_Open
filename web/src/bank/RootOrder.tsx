/**
 * 순서 맞추기(2026-11-18 사용자 「순서 맞추기 화면」, docs/changes/2026-11-18-ordering-screen).
 * 순서가 곧 내용인 나열 문항(예: 「폭스바이러스의 복제주기 단계는?」)을 「모두 고르기」 대신 단계를 차례로 눌러 푼다.
 * 단계 번호는 섞인 자리 그대로 고정이라 숫자 키로 누를 수 있다. 놓은 단계를 다시 누르면 그 단계만 빠진다.
 * 답을 본 뒤에는 자리마다 내 순서와 정답 순서를 나란히 보인다. 평가는 지금처럼 네 버튼이다(자동 채점 없음).
 */
type Item = { id: string; text: string };

export function orderScore(placed: string[], correct: string[]) {
  return { right: correct.filter((id, i) => placed[i] === id).length, total: correct.length };
}

export function RootOrder({ items, placed, correct, disabled, onToggle }: {
  items: Item[]; placed: string[];
  /** 올바른 순서(ID). 답을 본 뒤에만 있다. */
  correct?: string[];
  disabled: boolean; onToggle: (id: string) => void;
}) {
  const byId = new Map(items.map(item => [item.id, item]));
  if (correct?.length) {
    const score = orderScore(placed, correct);
    return (
      <div className="mq-order is-answered">
        <p className={`bank-choice-score ${score.right === score.total ? "is-correct" : "is-wrong"}`} role="status">
          <strong>{score.right === score.total ? "순서를 모두 맞혔어요!" : placed.length ? "순서가 달라요." : "놓은 단계가 없어요."}</strong>
          <span>맞은 자리 {score.right} / 전체 {score.total}</span>
        </p>
        <ol className="mq-order-compare" aria-label="자리별 내 순서와 정답 순서">
          {correct.map((id, i) => {
            const mine = placed[i];
            const state = !mine ? "is-empty" : mine === id ? "is-correct" : "is-wrong";
            return (
              <li key={id} className={state}>
                <span className="mq-order-mark" aria-hidden="true">{state === "is-correct" ? "✓" : state === "is-wrong" ? "✕" : "—"}</span>
                <span className="mq-order-right"><b>{i + 1}</b> {byId.get(id)?.text}</span>
                <span className="mq-order-mine">{mine ? state === "is-correct" ? "내 순서도 같음" : `내 순서: ${byId.get(mine)?.text ?? ""}` : "내 순서: 비어 있음"}</span>
              </li>
            );
          })}
        </ol>
      </div>
    );
  }
  return (
    <div className="mq-order">
      <p className="bank-note">단계를 일어나는 순서대로 누르세요. 놓은 단계를 다시 누르면 빠집니다.</p>
      <ul className="bank-options mq-order-pool">
        {items.map((item, index) => {
          const at = placed.indexOf(item.id);
          return (
            <li key={item.id}>
              <button type="button" className={`bank-option${at >= 0 ? " is-picked" : ""}`} disabled={disabled}
                aria-pressed={at >= 0} aria-keyshortcuts={index < 9 ? String(index + 1) : undefined} onClick={() => onToggle(item.id)}>
                <b>{index + 1}</b> {item.text}
                {at >= 0 ? <span className="mq-order-at">{at + 1}번째</span> : null}
              </button>
            </li>
          );
        })}
      </ul>
      <div className="mq-order-placed" aria-live="polite">
        <span className="mq-order-label">내 순서</span>
        {placed.length ? (
          <ol>{placed.map(id => <li key={id}>{byId.get(id)?.text}</li>)}</ol>
        ) : <span className="bank-note">아직 놓은 단계가 없습니다.</span>}
        {placed.length ? <kbd title="마지막 단계 빼기">Backspace</kbd> : null}
      </div>
    </div>
  );
}
