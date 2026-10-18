/** Keep only a few recent slides; reuse the exact signed URL so the browser can
 * share an in-flight download with the image that appears after revealing. */
export class SlidePreloader {
  private images = new Map<string, { image: HTMLImageElement; at: number }>();

  private reusable(entry: { image: HTMLImageElement; at: number }): boolean {
    // Downloaded pixels do not expire with the signed URL. Keep the actual node
    // so attaching it never starts another request, even with Cache-Control: no-store.
    return (entry.image.complete && entry.image.naturalWidth > 0) || Date.now() - entry.at < 45_000;
  }

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
      if (old && this.reusable(old)) {
        this.images.delete(key);
        this.images.set(key, old);
        continue;
      }
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
    return entry && this.reusable(entry) ? entry.image.src : url;
  }

  get(url: string): HTMLImageElement | undefined {
    const entry = this.images.get(this.key(url));
    return entry && this.reusable(entry) && !entry.image.isConnected ? entry.image : undefined;
  }
}
