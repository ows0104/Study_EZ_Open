/**
 * 노트 블록 HTML 정리. 편집기가 만드는 서식(굵게·기울임·밑줄·취소선·코드·글자색·배경색)만 남긴다.
 * 저장된 값을 innerHTML로 그리기 전에 반드시 거친다.
 */

const TAGS = new Set(["B", "STRONG", "I", "EM", "U", "S", "STRIKE", "DEL", "CODE", "SPAN", "FONT", "BR", "DIV"]);
const DROP = new Set(["SCRIPT", "STYLE", "TEMPLATE", "NOSCRIPT", "IFRAME", "OBJECT", "SVG", "MATH"]);
const STYLES = ["color", "background-color", "font-weight", "font-style", "text-decoration", "text-decoration-line"];
const SAFE_VALUE = /^[#(),.%\s\w-]*$/;

function cleanNode(node: Node, doc: Document): Node[] {
  if (node.nodeType === Node.TEXT_NODE) return [doc.createTextNode((node as Text).data)];
  if (node.nodeType !== Node.ELEMENT_NODE) return [];
  const el = node as HTMLElement;
  // SVG·MathML 요소는 tagName이 소문자다.
  const tag = el.tagName.toUpperCase();
  if (DROP.has(tag)) return [];
  const children = Array.from(el.childNodes).flatMap((c) => cleanNode(c, doc));
  if (!TAGS.has(tag) || !(el instanceof HTMLElement)) return children;
  const out = doc.createElement(tag.toLowerCase());
  const style = STYLES.map((p) => [p, el.style.getPropertyValue(p)] as const)
    .filter(([, v]) => v && SAFE_VALUE.test(v) && !/url|expression/i.test(v))
    .map(([p, v]) => `${p}: ${v};`)
    .join(" ");
  if (style) out.setAttribute("style", style);
  if (tag === "FONT") {
    const color = el.getAttribute("color");
    if (color && /^#?\w+$/.test(color)) out.setAttribute("color", color);
  }
  out.append(...children);
  return [out];
}

export function sanitizeNoteHtml(html: string): string {
  if (!html) return "";
  const doc = new DOMParser().parseFromString(`<body>${html}</body>`, "text/html");
  const holder = document.createElement("div");
  holder.append(...Array.from(doc.body.childNodes).flatMap((n) => cleanNode(n, document)));
  return holder.innerHTML;
}
