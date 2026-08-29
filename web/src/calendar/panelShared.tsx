

/**
 * 패널의 두 갈래가 같이 쓰는 조각.
 *
 * `PreviewAction`(예습 링크)과 `DeckSlot`(덱 만들기)이 둘 다 "다시 만들까?"를
 * 물어야 해서, 그 확인 UI 가 어느 한쪽에 살면 다른 쪽이 그쪽을 import 하게 된다.
 * 두 갈래는 서로를 몰라야 하므로 여기로 뺐다.
 */
/**
 * 다시 만들기.
 *
 * 링크를 여는 것에 견주면 드물게 하는 일이라 아이콘 하나로 줄여 링크 옆에
 * 붙인다. 아래에 한 줄로 두면 그 줄이 링크만큼 눈에 걸린다.
 *
 * 이름이 화면에 안 나오므로 `aria-label`과 `title`이 그것을 대신한다 — 아이콘
 * 하나만으로는 무엇이 다시 만들어지는지 알 수 없다.
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
  /** 도는 동안 읽어 주는 말. 링크는 「여는 중」이고 덱은 「만드는 중」이다. */
  busyLabel?: string;
  disabled: boolean;
  onClick: () => void;
}) {
  return (
    <button
      className={busy ? "panel-remake is-busy" : "panel-remake"}
      onClick={onClick}
      disabled={disabled}
      aria-label={busy ? busyLabel : label}
      aria-busy={busy}
      title={label}
    >
      <span aria-hidden="true">⟳</span>
    </button>
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
