import { useEffect, useRef, useState, type ReactNode } from "react";

/**
 * 개인 대화 버튼(2026-11-07 사용자 선택 C안).
 *
 * 왼쪽 큰 칸은 원래 하던 일 그대로다 — 처음에는 새 대화 만들기(＋), 그 뒤에는 대화 열기(↗).
 * 오른쪽 ▾를 누르면 「새 대화 만들기」(대화가 있을 때)·「내 프롬프트 수정」이 펼쳐진다.
 * 메뉴 밖을 누르거나 Esc면 닫는다.
 */
export function ChatSplit({
  tone,
  main,
  onRemake,
  remakeDisabled,
  onPrompt,
  promptOpen,
  promptCustom,
}: {
  tone: "pre" | "review";
  /** 왼쪽 칸. `className="chat-split-main"`인 a·button·span */
  main: ReactNode;
  /** 대화가 이미 있을 때만 준다 */
  onRemake?: () => void;
  remakeDisabled?: boolean;
  onPrompt: () => void;
  promptOpen: boolean;
  promptCustom?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDown = (event: MouseEvent) => {
      if (!box.current?.contains(event.target as Node)) setOpen(false);
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.stopPropagation();
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", onDown);
    window.addEventListener("keydown", onKey, true);
    return () => {
      document.removeEventListener("mousedown", onDown);
      window.removeEventListener("keydown", onKey, true);
    };
  }, [open]);

  return (
    <span className={`chat-split is-${tone}`} ref={box}>
      {main}
      <button
        type="button"
        className={`chat-split-side${promptCustom ? " is-dot" : ""}`}
        aria-label="개인 대화 메뉴"
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen(value => !value)}
      >
        ▾
      </button>
      {open ? (
        <span className="chat-split-menu" role="menu">
          {onRemake ? (
            <button type="button" role="menuitem" disabled={remakeDisabled} onClick={() => { setOpen(false); onRemake(); }}>
              <span aria-hidden="true">＋</span>새 대화 만들기
            </button>
          ) : null}
          <button type="button" role="menuitem" onClick={() => { setOpen(false); onPrompt(); }}>
            <span aria-hidden="true">✎</span>{promptOpen ? "내 프롬프트 접기" : "내 프롬프트 수정"}
          </button>
        </span>
      ) : null}
    </span>
  );
}
