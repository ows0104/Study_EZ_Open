import { useState } from "react";
import { api } from "../api";
import { absoluteUrl, extensionInstalled, extensionPossible, requestPreview } from "../bridge/previewBridge";
import { EXTENSION_DOWNLOAD_URL, EXTENSION_STORE_URL } from "../bridge/protocol";
import type { LectureDetail, LectureRef } from "../types/lectures";
import { ActionCard, PanelGroup } from "./panelShared";

/** 올해 강의록으로 복습한다. 예습 대화와 문제은행에서 독립된 개인 대화다. */
export function ReviewAction({ lecture, detail, base, onError }: {
  lecture: Pick<LectureRef, "subject" | "runId">;
  detail: LectureDetail;
  base: string;
  onError: (message: string) => void;
}) {
  const [busy, setBusy] = useState(false);
  const notes = detail.files.find((file) => file.kind === "notes_current");
  const saved = detail.myReview;
  const installed = extensionInstalled();

  async function start() {
    if (!notes || busy) return;
    setBusy(true);
    try {
      const sources = [notes, ...detail.files.filter((file) => file.kind === "jokbo")];
      const files = await Promise.all(sources.map(async (file) => {
        const { url } = await api<{ url: string }>(`${base}/files/${file.id}`);
        return { id: file.id, filename: file.filename, downloadUrl: absoluteUrl(url), contentType: file.contentType };
      }));
      await requestPreview({
        requestId: `${lecture.runId}-review-${performance.now()}`,
        lectureId: `${lecture.subject}/${lecture.runId}`,
        provider: saved?.provider ?? "chatgpt",
        mode: "review",
        prompt: [
          notes.filename,
          "오늘 들은 강의를 복습하고 싶어. 첨부한 올해 강의록을 바탕으로 핵심 개념과 흐름을 정리하고, 헷갈리기 쉬운 개념의 차이를 설명해줘. 중요한 내용은 강의록의 해당 페이지와 연결해줘. 족보가 있으면 출제되는 개념을 확인하는 데 참고해줘. 마지막에는 내가 이해했는지 확인할 짧은 질문을 하나씩 물어봐줘.",
        ].join("\n"),
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
    <PanelGroup tone="preview" title="복습" note="오늘 강의록을 다시 읽는 대화">
      <ActionCard shape={`is-key is-review${saved || notes && installed ? "" : " is-empty"}`}
        hit={saved ? (
          <a className="panel-action-hit" href={saved.conversationUrl} target="_blank" rel="noreferrer">
            <strong>개인 링크</strong><small>복습 대화 열기</small>
          </a>
        ) : notes && installed ? (
          <button className="panel-action-hit" disabled={busy} onClick={() => void start()}>
            <strong>개인 링크</strong><small>{busy ? "여는 중…" : "만들기"}</small>
          </button>
        ) : (
          <span className="panel-action-hit">
            <strong>개인 링크</strong>
            <small>{!notes ? "올해 강의록 대기" : extensionPossible() ? "확장을 설치하면 만듭니다" : "컴퓨터에서 만듭니다"}</small>
          </span>
        )} />
      {notes && !installed && !saved && extensionPossible() ? (
        <p className="panel-hint">
          <a href={EXTENSION_STORE_URL || EXTENSION_DOWNLOAD_URL} target="_blank" rel="noreferrer">브리지 설치</a> 후 이 탭을 새로고침해 주세요.
        </p>
      ) : null}
    </PanelGroup>
  );
}
