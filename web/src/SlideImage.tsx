import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import type { SlidePreloader } from "./slidePreload";

function ExpandedSlide({ src, alt, onClose }: { src: string; alt: string; onClose: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => { dialog.current?.showModal(); }, []);
  return createPortal(<dialog ref={dialog} className="slide-image-dialog" aria-label={`${alt} 확대`}
    onCancel={event => { event.preventDefault(); onClose(); }}
    onClick={event => { if (event.target === event.currentTarget) onClose(); }}>
    <div className="slide-image-expanded">
      <button type="button" className="slide-image-close" onClick={onClose} autoFocus aria-label="확대 사진 닫기">닫기 ×</button>
      <img src={src} alt={alt} />
    </div>
  </dialog>, document.body);
}

export function SlideImage({ src, alt, preload }: {
  src: string; alt: string; preload?: SlidePreloader;
}) {
  const host = useRef<HTMLSpanElement>(null);
  const [expanded, setExpanded] = useState(false);
  useLayoutEffect(() => {
    const image = preload?.get(src) ?? new Image();
    const retry = () => {
      const fresh = new URL(src, window.location.href).href;
      if (image.src !== fresh) image.src = fresh;
    };
    image.className = "quiz-slide";
    image.alt = alt;
    image.loading = "eager";
    image.fetchPriority = "high";
    image.addEventListener("error", retry, { once: true });
    if (!image.src) image.src = src;
    host.current?.appendChild(image);
    return () => {
      image.removeEventListener("error", retry);
      image.remove();
    };
  }, [src, alt, preload]);
  return <>
    <button type="button" className="slide-image-open" aria-label={`${alt} 크게 보기`} onClick={() => setExpanded(true)}>
      <span ref={host} style={{ display: "contents" }} />
    </button>
    {expanded ? <ExpandedSlide src={src} alt={alt} onClose={() => setExpanded(false)} /> : null}
  </>;
}
