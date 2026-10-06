import { useLayoutEffect, useRef } from "react";
import type { SlidePreloader } from "./slidePreload";

export function SlideImage({ src, alt, preload }: {
  src: string; alt: string; preload?: SlidePreloader;
}) {
  const host = useRef<HTMLDivElement>(null);
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
  return <div ref={host} style={{ display: "contents" }} />;
}
