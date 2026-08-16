import { Fragment } from "react";

/**
 * 발문의 `**강조**`를 살려서 그린다.
 *
 * 출제 규칙이 부정형 발문("…해당하지 **않는 것은**?")을 놓치지 말라고 넣은
 * 표시다. 평문으로 흘리면 별표만 보이고, 지우면 강조가 사라진다. 마크다운
 * 라이브러리를 들이지 않는 이유는 살릴 문법이 이것 하나이기 때문이다.
 */
export function Stem({ text }: { text: string }) {
  return (
    <>
      {text.split(/(\*\*[^*]+\*\*)/g).map((part, index) =>
        part.startsWith("**") && part.endsWith("**") && part.length > 4 ? (
          <strong key={index}>{part.slice(2, -2)}</strong>
        ) : (
          <Fragment key={index}>{part}</Fragment>
        ),
      )}
    </>
  );
}
