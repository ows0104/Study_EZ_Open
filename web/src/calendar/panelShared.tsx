import type { ReactNode } from "react";

/**
 * 패널의 두 갈래가 같이 쓰는 조각.
 *
 * `PreviewAction`(예습 링크)과 `DeckSlot`(덱 만들기)이 둘 다 "다시 만들까?"를
 * 물어야 해서, 그 확인 UI 가 어느 한쪽에 살면 다른 쪽이 그쪽을 import 하게 된다.
 * 두 갈래는 서로를 몰라야 하므로 여기로 뺐다.
 */
/**
 * 갈래 하나를 묶는 자리. 예습 · Pre-Quiz · Main-Quiz.
 *
 * **머리에 이름과 색을 단다.** 전에는 셋이 같은 파랑 버튼으로 이어져 있어서
 * 어디까지가 예습이고 어디부터가 Pre-Quiz인지 글자를 읽어야 알았다. 색은 갈래만
 * 진다 — 있다/없다/만드는 중은 여전히 테두리 꼴과 글이 말한다.
 *
 * `fold` 는 **접힌 채로 서는 칸**이다(2026-09-18 관리자 지시 - 모아받기가
 * 의도보다 눈에 띈다). 머리 줄이 그대로 여닫는 손잡이가 되고, 안의 것은 열어야
 * 보인다. 갈래 셋은 이 패널이 하라는 일 자체라 접지 않는다.
 */
export function PanelGroup({
  tone,
  title,
  note,
  fold = false,
  children,
}: {
  /**
   * `is-preview` · `is-pre` · `is-main`. 색은 CSS 가 고른다.
   *
   * `plain` 은 **셋 중 어느 갈래도 아닌 것**이다(모아받기 — 예습과 복습을 같이
   * 든다). 갈래가 아니므로 갈래 색도 안 진다 — 회색이다(2026-09-18 관리자 지시).
   * 그 전에는 기본색이 `--accent` 라 `--fam-main` 과 값이 같았고, 화면에서 이 칸이
   * Main-Quiz 와 똑같이 나왔다. **갈래가 아닌 것이 갈래 색을 얻으면 그때부터
   * 무엇을 뜻하는지 알 수 없다** — 색을 되돌리지 마라.
   */
  tone: "preview" | "pre" | "main" | "bank" | "plain";
  title: string;
  note?: string;
  /** 접힌 채로 설 것인가. 머리 줄이 여닫는 손잡이가 된다. */
  fold?: boolean;
  children: ReactNode;
}) {
  /* 접는 쪽은 `<details>` 다. 여닫힌 상태를 React 가 들면 패널이 칸을 갈아탈
     때마다 「열어 둔 것을 닫을까」를 따로 정해야 하는데, 브라우저의 것을 쓰면
     칸을 닫을 때 같이 사라지고 다시 열면 접힌 채로 뜬다 - 여기서 바라는 그대로다. */
  if (fold) {
    return (
      <details className={`panel-group is-${tone} is-fold`}>
        <summary className="panel-group-head">
          <span>{title}</span>
          {note ? <small>{note}</small> : null}
        </summary>
        {children}
      </details>
    );
  }

  return (
    <section className={`panel-group is-${tone}`}>
      <h3 className="panel-group-head">
        <span>{title}</span>
        {note ? <small>{note}</small> : null}
      </h3>
      {children}
    </section>
  );
}

/**
 * 자료 버튼 한 장.
 *
 * **카드 전체가 하나의 큰 과녁이고, 그 안에 작은 버튼이 든다**(2026-08-31 관리자
 * 지시 — 따로 아래 줄에 두지 말고 버튼 안에 넣어라).
 *
 * `<button>` 안에 `<button>`은 HTML이 허용하지 않는다 — 브라우저가 DOM을 다시
 * 짜서 작은 버튼이 카드 밖으로 튀어나온다. 그래서 카드는 틀(`div`)이고, 큰
 * 과녁은 그 안에서 `::before`로 카드를 통째로 덮는 `panel-action-hit`이다.
 * 작은 버튼은 그 위에 얹힌다. 둘 다 진짜 컨트롤이라 Tab 순서도 그대로 산다.
 */
export function ActionCard({
  shape = "",
  hit,
  tools,
}: {
  /** `is-key` · `is-lead` · `is-compact` · `is-empty` · `is-download` 같은 꼴 표시. */
  shape?: string;
  /** 카드를 통째로 쓰는 것. `panel-action-hit`을 달고 온다. */
  hit: ReactNode;
  /** 카드 안에 드는 작은 버튼들. 없으면 줄 자체가 안 선다. */
  tools?: ReactNode;
}) {
  return (
    <div className={`panel-action ${shape}`.trimEnd()}>
      {hit}
      {tools ? <div className="panel-nested">{tools}</div> : null}
    </div>
  );
}

/**
 * 작은 버튼 하나.
 *
 * **이름을 버튼 안에 적는다(2026-08-31 관리자 지시).** 전에는 `✎`·`⟳` 아이콘만
 * 링크 옆에 붙어 있었고, 무엇이 고쳐지고 무엇이 다시 만들어지는지는 마우스를
 * 올려 `title`을 띄워 봐야 알았다. 손가락으로 누르는 화면에는 그 방법이 없다.
 *
 * 자리는 둘이다 — **자기가 손대는 카드 안**(`ActionCard`의 `tools`)이거나,
 * 어느 한 카드의 것이 아니면 **갈래의 오른쪽 아래**(`.panel-aside`)다.
 */
export function PanelTool({
  icon,
  label,
  hint,
  busy = false,
  busyLabel,
  disabled = false,
  active = false,
  dot = false,
  expanded,
  onClick,
}: {
  icon: string;
  label: string;
  /**
   * 읽어 주는 말. 카드 안은 좁아서 글씨를 줄이는데, 그때 무엇이 다시
   * 만들어지는지는 여기가 온전히 말한다. 안 주면 `label`이 그 자리다.
   */
  hint?: string;
  busy?: boolean;
  /** 도는 동안 대신 읽는 말. 링크는 「여는 중」이고 덱은 「만드는 중」이다. */
  busyLabel?: string;
  disabled?: boolean;
  /** 지금 펼쳐져 있는가(프롬프트 편집칸). */
  active?: boolean;
  /** 기본값이 아닌 것이 저장돼 있는가. 점 하나로만 말한다. */
  dot?: boolean;
  expanded?: boolean;
  onClick: () => void;
}) {
  const text = busy ? busyLabel || "여는 중…" : label;
  const full = busy ? text : hint || label;
  return (
    <button
      className={`panel-tool${active ? " is-active" : ""}${dot ? " is-dot" : ""}${busy ? " is-busy" : ""}`}
      onClick={onClick}
      disabled={disabled}
      aria-busy={busy}
      aria-expanded={expanded}
      aria-label={full}
      title={full}
    >
      {/* 쉬는 자리에서는 글씨 하나가 전부다. 아이콘이 도는 것은 그것 자체가
          「지금 돌고 있다」는 말이라 그때만 나온다. */}
      {busy ? (
        <span className="panel-tool-icon" aria-hidden="true">
          {icon}
        </span>
      ) : null}
      {text}
    </button>
  );
}

/**
 * 다시 만들기. 카드 안에 드는 `PanelTool` 한 종류다.
 *
 * 아이콘 하나로 줄여 링크 옆에 붙여 두었던 것을 글씨가 있는 버튼으로 폈고, 그
 * 버튼을 자기가 다시 만드는 카드 안으로 넣었다 — 무엇이 다시 만들어지는지를
 * 자리가 먼저 말한다.
 */
export function Remake({
  label,
  hint,
  busy,
  busyLabel = "여는 중…",
  disabled,
  onClick,
}: {
  label: string;
  hint?: string;
  busy: boolean;
  busyLabel?: string;
  disabled: boolean;
  onClick: () => void;
}) {
  return (
    <PanelTool
      icon="⟳"
      label={label}
      hint={hint}
      busy={busy}
      busyLabel={busyLabel}
      disabled={disabled}
      onClick={onClick}
    />
  );
}

/**
 * 되돌리기 어려운 것을 다시 만들기 전에 한 번 묻는다.
 *
 * 기본 링크는 반 전체가 보는 값이고, Pre-Quiz 덱은 한 편에 15분과 빈 세션 넷이
 * 든다. 둘 다 눌러 버린 뒤에 무르는 길이 없다.
 *
 * `window.confirm` 대신 자리에서 묻는다 — 새 탭을 여는 흐름이라 모달이 팝업
 * 차단과 얽히고, 무엇을 바꾸는지 문장으로 적을 자리도 없다.
 */
export function RemakeConfirm({
  message,
  confirm = "바꾸기",
  onConfirm,
  onCancel,
}: {
  message: string;
  confirm?: string;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  return (
    <div className="panel-confirm">
      <p>{message}</p>
      <div className="panel-confirm-actions">
        <button onClick={onConfirm}>{confirm}</button>
        <button className="is-quiet" onClick={onCancel}>
          취소
        </button>
      </div>
    </div>
  );
}

/** 1MB 아래를 `0.0MB`로 적으면 크기를 말한 것이 아니라 안 말한 것이 된다. */
export function fileSize(bytes: number) {
  return bytes < 1024 * 1024 ? `${Math.max(1, Math.round(bytes / 1024))}KB` : `${(bytes / 1024 / 1024).toFixed(1)}MB`;
}
