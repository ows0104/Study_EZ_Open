import { DEFAULT_PREVIEW_PROMPT } from "./previewPrompt";
import { usePersonalPrompt } from "./usePersonalPrompt";

export function usePreviewPrompt() {
  return usePersonalPrompt("preview", DEFAULT_PREVIEW_PROMPT);
}
