import type { SlidePreloader } from "./slidePreload";

export function SlideImage({ src, alt, preload }: {
  src: string; alt: string; preload?: SlidePreloader;
}) {
  const prepared = preload?.resolve(src) ?? src;
  return <img className="quiz-slide" src={prepared} alt={alt} loading="eager" decoding="async"
    onError={(event) => {
      // If a speculative signed URL failed, retry the fresh reveal URL once.
      const fresh = new URL(src, window.location.href).href;
      if (event.currentTarget.src !== fresh) event.currentTarget.src = fresh;
    }} />;
}
