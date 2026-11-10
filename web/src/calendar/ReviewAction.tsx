import { useState, type ReactNode } from "react";
import { ChatSplit } from "./ChatSplit";
import { api } from "../api";
import { absoluteUrl, extensionCompatible, extensionInstalled, extensionPossible, requestPreview } from "../bridge/previewBridge";
import { ExtensionSetup } from "../bridge/ExtensionSetup";
import type { LectureDetail, LectureRef } from "../types/lectures";
import { PromptEditor } from "./PromptEditor";
import { DEFAULT_REVIEW_PROMPT, REVIEW_PROMPT_TOKENS, renderReviewPrompt } from "../lecture/reviewPrompt";
import { usePersonalPrompt } from "../lecture/usePersonalPrompt";
import type { PreviewProvider } from "../types/lectures";
import { ActionCard, PanelGroup } from "./panelShared";

/** 올해 강의록으로 복습한다. 예습 대화와 문제은행에서 독립된 개인 대화다. */
export function ReviewAction({ lecture, detail, base, onError, trailing, open }: {
  lecture: Pick<LectureRef, "subject" | "runId">;
  detail: LectureDetail;
  base: string;
  onError: (message: string) => void;
  /** 같은 줄 끝에 붙는 버튼(2026-11 개편: 「복습 퀴즈」). */
  trailing?: ReactNode;
  /** 참이면 링크가 없어도 접지 않는다(강의 패널). */
  open?: boolean;
}) {
  const [busy, setBusy] = useState(false);
  const [showPrompt, setShowPrompt] = useState(false);
  const [provider, setProvider] = useState<PreviewProvider>(detail.myReview?.provider ?? "chatgpt");
  const promptStore = usePersonalPrompt("review", DEFAULT_REVIEW_PROMPT);
  const notes = detail.files.find((file) => file.kind === "notes_current");
  const saved = detail.myReview;
  const installed = extensionInstalled();
  const compatible = extensionCompatible();

  async function start() {
    if (!notes || busy || !promptStore.loaded) return;
    setBusy(true);
    try {
      const sources = [notes, ...detail.files.filter((file) => file.kind === "jokbo")];
      const files = await Promise.all(sources.map(async (file) => {
        const { url } = await api<{ url: string }>(`${base}/files/${file.id}?purpose=review_attach`);
        return { id: file.id, filename: file.filename, downloadUrl: absoluteUrl(url), contentType: file.contentType };
      }));
      await requestPreview({
        requestId: `${lecture.runId}-review-${performance.now()}`,
        lectureId: `${lecture.subject}/${lecture.runId}`,
        provider,
        mode: "review",
        prompt: renderReviewPrompt(promptStore.template, detail),
        files,
        autoSend: false,
      });
    } catch (cause) {
      onError((cause as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <PanelGroup tone="review" title="복습" fold={!saved && !open}
      note={saved ? "오늘 강의록을 다시 읽는 대화" : "개인 링크 만들기"}>
      {/* C안(2026-11-07): 왼쪽은 처음엔 만들기(＋), 그 뒤엔 열기(↗). ▾에 새 대화 만들기·내 프롬프트 수정. */}
      {saved ? (
        <ChatSplit tone="review" linked
          main={<a className="chat-split-main" href={saved.conversationUrl} target="_blank" rel="noreferrer"><span aria-hidden="true">↗</span>개인 대화</a>}
          onRemake={notes && installed ? () => void start() : undefined}
          remakeDisabled={busy || !compatible || !promptStore.loaded}
          onPrompt={() => setShowPrompt(open => !open)} promptOpen={showPrompt} />
      ) : notes && installed ? (
        <ChatSplit tone="review"
          main={
            <button type="button" className="chat-split-main" aria-label="개인 대화 만들기"
              disabled={busy || !compatible || !promptStore.loaded} onClick={() => void start()}>
              <span aria-hidden="true">＋</span>{busy ? "여는 중…" : "개인 대화"}
            </button>
          }
          onPrompt={() => setShowPrompt(open => !open)} promptOpen={showPrompt} />
      ) : (
        <ActionCard shape="is-key is-faint is-empty"
          hit={<span className="panel-action-hit"><strong>개인 대화</strong>
            <small>{!notes ? "올해 강의록 대기" : extensionPossible() ? "확장을 설치하면 만듭니다" : "컴퓨터에서 만듭니다"}</small></span>} />
      )}
      {trailing}
      {promptStore.error && !showPrompt ? <p className="prompt-editor-error">{promptStore.error}</p> : null}
      {showPrompt ? <PromptEditor store={promptStore} detail={detail} provider={provider} onProvider={setProvider}
        kind="review" render={renderReviewPrompt} tokens={REVIEW_PROMPT_TOKENS} /> : null}
      {notes && !saved ? <ExtensionSetup /> : null}
    </PanelGroup>
  );
}
