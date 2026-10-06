/** Keep only a few recent slides; reuse the exact signed URL so the browser can
 * share an in-flight download with the image that appears after revealing. */
export class SlidePreloader {
  private images = new Map<string, { image: HTMLImageElement; at: number }>();

  private key(url: string): string {
    // Ignore S3 signing parameters, but preserve resource/transform parameters.
    const parsed = new URL(url, window.location.href);
    for (const name of [...parsed.searchParams.keys()]) {
      if (name.toLowerCase().startsWith("x-amz-")) parsed.searchParams.delete(name);
    }
    parsed.searchParams.sort();
    return parsed.href;
  }

  warm(urls: string[]) {
    for (const url of urls) {
      const key = this.key(url);
      const old = this.images.get(key);
      if (old && Date.now() - old.at < 45_000) continue;
      const image = new Image();
      image.decoding = "async";
      image.fetchPriority = "low";
      const entry = { image, at: Date.now() };
      this.images.delete(key);
      this.images.set(key, entry);
      image.onerror = () => {
        if (this.images.get(key) === entry) this.images.delete(key);
      };
      image.src = url;
      // Decode while the question is being read, without delaying its text.
      void image.decode().catch(() => {});
      while (this.images.size > 12) this.images.delete(this.images.keys().next().value!);
    }
  }

  resolve(url: string): string {
    const entry = this.images.get(this.key(url));
    // The server permits signed lifetimes as short as 60 seconds.
    return entry && Date.now() - entry.at < 45_000 ? entry.image.src : url;
  }
}
