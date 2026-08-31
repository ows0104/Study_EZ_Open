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
 * `aside`는 머리 오른쪽에 눕는 것이다(예습의 AI 고르기).
 */
export function PanelGroup({
  tone,
  title,
  note,
  aside,
  children,
}: {
  /** `is-preview` · `is-pre` · `is-main`. 색은 CSS 가 고른다. */
  tone: "preview" | "pre" | "main";
  title: string;
  note?: string;
  aside?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section className={`panel-group is-${tone}`}>
      <h3 className="panel-group-head">
        <span>{title}</span>
        {note ? <small>{note}</small> : null}
        {aside}
      </h3>
      {children}
    </section>
  );
}

/**
 * 드물게 하는 일이 모이는 조용한 줄. 갈래마다 그 아래에 한 줄씩 선다.
 */
export function PanelTools({ children }: { children: ReactNode }) {
  return <div className="panel-tools">{children}</div>;
}

/**
 * 조용한 줄에 서는 버튼 하나.
 *
 * **이름을 버튼 안에 적는다(2026-08-31 관리자 지시).** 전에는 `✎`·`⟳` 아이콘만
 * 링크 옆에 붙어 있었고, 무엇이 고쳐지고 무엇이 다시 만들어지는지는 마우스를
 * 올려 `title`을 띄워 봐야 알았다. 손가락으로 누르는 화면에는 그 방법이 없다.
 */
export function PanelTool({
  icon,
  label,
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
  return (
    <button
      className={`panel-tool${active ? " is-active" : ""}${dot ? " is-dot" : ""}${busy ? " is-busy" : ""}`}
      onClick={onClick}
      disabled={disabled}
      aria-busy={busy}
      aria-expanded={expanded}
      title={text}
    >
      <span className="panel-tool-icon" aria-hidden="true">
        {icon}
      </span>
      {text}
    </button>
  );
}

/**
 * 다시 만들기. 조용한 줄에 서는 `PanelTool` 한 종류다.
 *
 * 아이콘 하나로 줄여 링크 옆에 붙여 두었던 것을 글씨가 있는 버튼으로 폈다 —
 * 자리는 갈래 아래 조용한 줄이라 여전히 링크만큼 눈에 걸리지는 않는다.
 */
export function Remake({
  label,
  busy,
  busyLabel = "여는 중…",
  disabled,
  onClick,
}: {
  label: string;
  busy: boolean;
  busyLabel?: string;
  disabled: boolean;
  onClick: () => void;
}) {
  return (
    <PanelTool icon="⟳" label={label} busy={busy} busyLabel={busyLabel} disabled={disabled} onClick={onClick} />
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
