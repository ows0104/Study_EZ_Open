import { useState } from "react";
import { api } from "../api";
import {
  absoluteUrl,
  extensionInstalled,
  requestPreview,
  watchSharedLink,
} from "../bridge/previewBridge";
import { EXTENSION_DOWNLOAD_URL, EXTENSION_STORE_URL } from "../bridge/protocol";
import {
  PROMPT_TOKENS,
  SHARED_PREVIEW_PROMPT,
  renderPreviewPrompt,
} from "../lecture/previewPrompt";
import { usePreviewPrompt } from "../lecture/usePreviewPrompt";
import {
  previewProviderLabels,
  previewProviders,
  type LectureDetail,
  type LectureRef,
  type PreviewProvider,
} from "../types";
import { useMe } from "../useMe";
import { PanelGroup, PanelTool, PanelTools, Remake, RemakeConfirm } from "./panelShared";

/**
 * 예습 링크 한 칸. 확장이 대화를 열고, 공유 링크가 돌아오면 그것을 붙든다.
 *
 * `EventPanel` 에서 갈라 나왔다 — 패널이 964줄이었고 그중 이 갈래가 가장 컸다.
 */
/**
 * 예습.
 *
 * 두 갈래다.
 *
 * **관리자가 이미 대화를 만들어 공유했으면** 그 대화를 읽는 것이 낫다. 정리된
 * 글이 있고, 그것이 곧 Pre-Quiz의 본체이기도 하다.
 *
 * **아직 없으면 작년 필기만 있어도 직접 시작할 수 있다.** 자료를 URL에 실을 수는
 * 없으므로 한 번에 셋을 한다 — 필기를 내려받고, 프롬프트를 복사하고, 선택한 AI를
 * 연다. 사용자는 전송만 하면 된다.
 *
 * 관리자가 이 길로 만든 대화를 `/admin`에 공유 링크로 넣으면 Pre-Quiz의 재료가
 * 된다. 화면은 같고 그 뒷일만 다르다.
 *
 * **둘은 한 행에 나란히 선다(2026-08-31 관리자 지시).** 위아래로 쌓아 두면 앞의
 * 것이 먼저고 뒤의 것이 딸린 것으로 보이는데, 사실은 고르는 것이다 — 반이 같이
 * 읽는 대화냐, 내 대화냐.
 */
export function PreviewAction({
  lecture,
  detail,
  base,
  onError,
}: {
  lecture: LectureRef;
  detail: LectureDetail;
  base: string;
  onError: (message: string) => void;
}) {
  const [busy, setBusy] = useState<"shared" | "personal" | "">("");
  const [askingRemake, setAskingRemake] = useState(false);
  const [showPrompt, setShowPrompt] = useState(false);
  const [provider, setProvider] = useState<PreviewProvider>(() =>
    detail.myPreview?.provider || detail.preview?.provider || "chatgpt"
  );
  const promptStore = usePreviewPrompt();
  const isAdmin = Boolean(useMe()?.isAdmin);
  const lectureId = `${lecture.subject}/${lecture.runId}`;
  const notesPrev = detail.files.find((file) => file.kind === "notes_prev");

  /**
   * 확장이 자료를 첨부하고 프롬프트를 채운다. 여기서는 어느 자료를 어느 강의로,
   * 어느 몫으로 여는지만 넘긴다 — 서명 URL은 수명이 짧아 누른 순간에 받는다.
   */
  async function start(mode: "shared" | "personal") {
    if (!notesPrev) return;
    setBusy(mode);
    try {
      const { url } = await api<{ url: string }>(`${base}/files/${notesPrev.id}`);
      await requestPreview({
        requestId: `${lecture.runId}-${performance.now()}`,
        lectureId,
        provider,
        mode,
        prompt: renderPreviewPrompt(mode === "shared" ? SHARED_PREVIEW_PROMPT : promptStore.template, detail),
        files: [{ id: notesPrev.id, filename: notesPrev.filename, downloadUrl: absoluteUrl(url) }],
      });
    } catch (cause) {
      onError((cause as Error).message);
    } finally {
      setBusy("");
    }
  }

  // 확장이 없으면 자동으로 열 수 없다. 기본 링크가 이미 있으면 그건 그냥 주소라
  // 확장 없이도 열린다 — 그 경우만 먼저 보여 준다.
  if (!extensionInstalled()) {
    const storeReady = Boolean(EXTENSION_STORE_URL);
    return (
      <PanelGroup tone="preview" title="예습" note="강의 전에 읽는 대화">
        {detail.preview?.shareUrl ? (
          <SharedOpen url={detail.preview.shareUrl} lectureId={lectureId} provider={detail.preview.provider} />
        ) : null}
        <a
          className="panel-action is-key is-download"
          href={storeReady ? EXTENSION_STORE_URL : EXTENSION_DOWNLOAD_URL}
          download={storeReady ? undefined : true}
          target={storeReady ? "_blank" : undefined}
          rel={storeReady ? "noreferrer" : undefined}
        >
          <strong>{storeReady ? "Chrome 웹스토어에서 설치" : "예습 브리지 내려받기"}</strong>
          <small>설치하면 필기와 프롬프트가 선택한 AI에 자동으로 들어갑니다</small>
        </a>
        {storeReady ? (
          <p className="panel-steps">설치한 뒤 이 탭을 새로고침해 주세요.</p>
        ) : (
          <ol className="panel-steps">
            <li>받은 zip을 압축 해제합니다.</li>
            <li>
              <code>chrome://extensions</code> → 오른쪽 위 <b>개발자 모드</b>
            </li>
            <li>
              <b>압축해제된 확장 프로그램을 로드</b> → 압축 푼 폴더
            </li>
            <li>이 탭을 새로고침합니다.</li>
          </ol>
        )}
      </PanelGroup>
    );
  }

  // 작년 필기가 없으면 새로 만들 수는 없다. 다만 이미 만들어진 링크는 그대로
  // 열려야 하므로 여기서 통째로 돌려보내지 않는다.
  const canMake = Boolean(notesPrev);
  const hasPersonal = Boolean(detail.myPreview?.conversationUrl);

  /* 기본 링크 — 강의당 하나, 반 전체가 같은 것을 읽는다. 문구가 고정이라
     누가 만들었든 같은 것을 물은 대화다. 만드는 것은 관리자뿐이다. */
  const shared = detail.preview?.shareUrl ? (
    <SharedOpen url={detail.preview.shareUrl} lectureId={lectureId} provider={detail.preview.provider} />
  ) : !canMake ? (
    <span className="panel-action is-key is-empty">
      <strong>기본 링크</strong>
      <small>작년 필기 대기</small>
    </span>
  ) : isAdmin ? (
    <button className="panel-action is-key" onClick={() => start("shared")} disabled={Boolean(busy)}>
      <strong>기본 링크</strong>
      <small>{busy === "shared" ? "여는 중…" : `만들기 · ${previewProviderLabels[provider]}`}</small>
    </button>
  ) : (
    <span className="panel-action is-key is-empty">
      <strong>기본 링크</strong>
      <small>아직 없습니다</small>
    </span>
  );

  /* 개인 링크 — 사람마다 하나. 프롬프트도 자기 것으로 묻는다. 그래서 프롬프트
     고치기가 이 갈래의 조용한 줄에 붙어 있다 — 기본 링크에는 안 듣는다. */
  const personal = detail.myPreview?.conversationUrl ? (
    /* 저장되면 이 자리가 회색 버튼("개인 예습 시작")에서 색이 든 줄로 바뀐다.
       색이 곧 "내 대화가 저장돼 있다"는 표시다.

       주소는 title에 그대로 둔다 — 빈 AI 창이 뜰 때 무엇이 저장돼 있는지
       볼 데가 여기밖에 없다. */
    <a
      className="panel-action is-key"
      href={detail.myPreview.conversationUrl}
      title={detail.myPreview.conversationUrl}
      target="_blank"
      rel="noreferrer"
    >
      <strong>개인 링크</strong>
      <small>{previewProviderLabels[detail.myPreview.provider]} · 내 대화</small>
    </a>
  ) : canMake ? (
    <button className="panel-action is-key is-faint" onClick={() => start("personal")} disabled={Boolean(busy)}>
      <strong>개인 링크</strong>
      <small>{busy === "personal" ? "여는 중…" : `만들기 · ${previewProviderLabels[provider]}`}</small>
    </button>
  ) : (
    <span className="panel-action is-key is-empty">
      <strong>개인 링크</strong>
      <small>작년 필기 대기</small>
    </span>
  );

  return (
    <PanelGroup
      tone="preview"
      title="예습"
      aside={
        <label className="preview-provider-select">
          <select
            aria-label="예습에 쓸 AI"
            value={provider}
            onChange={(event) => setProvider(event.target.value as PreviewProvider)}
          >
            {previewProviders.map((item) => <option value={item} key={item}>{previewProviderLabels[item]}</option>)}
          </select>
        </label>
      }
    >
      <div className="panel-pair">
        {shared}
        {personal}
      </div>

      {/* 드물게 하는 일. 이름을 버튼 안에 적는다 — 아이콘만 있을 때는 마우스를
          올려 봐야 무엇이 고쳐지는지 알았다(2026-08-31 관리자 지시). */}
      <PanelTools>
        <PanelTool
          icon="✎"
          label={showPrompt ? "프롬프트 접기" : "프롬프트 수정"}
          active={showPrompt}
          dot={promptStore.isCustom}
          expanded={showPrompt}
          onClick={() => setShowPrompt((open) => !open)}
        />
        {isAdmin && canMake ? (
          <Remake
            label="기본 링크 다시 만들기"
            busy={busy === "shared"}
            disabled={Boolean(busy)}
            onClick={() => setAskingRemake(true)}
          />
        ) : null}
        {hasPersonal && canMake ? (
          // 자기 것이라 묻지 않는다. 옛 대화는 해당 AI 서비스에 그대로 남아 있고
          // 여기서 가리키는 주소만 새것으로 바뀐다.
          <Remake
            label="개인 링크 새 대화"
            busy={busy === "personal"}
            disabled={Boolean(busy)}
            onClick={() => void start("personal")}
          />
        ) : null}
      </PanelTools>

      {askingRemake ? (
        <RemakeConfirm
          message="모두가 보는 링크가 새 대화로 바뀝니다. 옛 링크는 기존 AI 서비스에 그대로 남지만 여기서는 안 보입니다."
          onConfirm={() => {
            setAskingRemake(false);
            void start("shared");
          }}
          onCancel={() => setAskingRemake(false)}
        />
      ) : null}
      {showPrompt ? <PromptEditor store={promptStore} detail={detail} /> : null}
    </PanelGroup>
  );
}

/**
 * 기본 링크 열기. `/share/`라 로그인도 확장도 없이 열린다.
 *
 * 여는 김에 확장에 어느 강의인지 일러 둔다. 공유 페이지에서 이어 물으면 새
 * 대화가 갈라져 나오는데, 그것이 그 사람의 개인 링크가 된다.
 */
function SharedOpen({
  url,
  lectureId,
  provider,
}: {
  url: string;
  lectureId: string;
  provider: PreviewProvider;
}) {
  return (
    <a
      className="panel-action is-key"
      href={url}
      target="_blank"
      rel="noreferrer"
      onClick={() => watchSharedLink(lectureId, provider, url)}
    >
      <strong>기본 링크</strong>
      <small>{previewProviderLabels[provider]} · 공통</small>
    </a>
  );
}

/**
 * 프롬프트 편집.
 *
 * 사람마다 예습하는 방식이 달라서 각자 고쳐 쓰고, 고친 것은 계정에 남는다.
 * 강의 이름 같은 값은 자리표시자로 남겨 둔다 — 안 그러면 고친 순간 모든 강의가
 * 한 강의의 이름을 달고 나간다.
 *
 * 미리보기는 지금 열어 둔 강의로 채워 보여 준다. 토큰이 실제로 무엇으로 바뀌는지
 * 눈으로 확인하지 않으면 자리표시자를 지워 버리기 쉽다.
 */
function PromptEditor({
  store,
  detail,
}: {
  store: ReturnType<typeof usePreviewPrompt>;
  detail: LectureDetail;
}) {
  const [draft, setDraft] = useState<string | null>(null);
  const [error, setError] = useState("");
  const text = draft ?? store.template;
  const dirty = draft !== null && draft.trim() !== store.template.trim();

  async function save() {
    setError("");
    try {
      await store.save(text);
      setDraft(null);
    } catch (cause) {
      setError((cause as Error).message);
    }
  }

  async function reset() {
    setError("");
    try {
      await store.reset();
      setDraft(null);
    } catch (cause) {
      setError((cause as Error).message);
    }
  }

  return (
    <div className="prompt-editor">
      {/* 기본 링크의 문구는 여기 안 나온다. 고칠 수 없는 것을 편집칸 위에
          펼쳐 두면 무엇을 고치는 화면인지 흐려진다(2026-08-22 관리자 지시). */}
      <h4 className="prompt-editor-label">개인 링크 — 내가 고쳐 쓰는 것</h4>
      <textarea
        className="prompt-editor-text"
        value={text}
        spellCheck={false}
        onChange={(event) => setDraft(event.target.value)}
        aria-label="예습 프롬프트"
      />
      <p className="prompt-editor-tokens">
        {PROMPT_TOKENS.map(({ token, label }) => (
          <button
            key={token}
            type="button"
            title={`${label} 넣기`}
            onClick={() => setDraft(`${text}${text.endsWith("\n") ? "" : " "}${token}`)}
          >
            {token}
          </button>
        ))}
        <span>누르면 끝에 붙습니다</span>
      </p>
      <div className="prompt-editor-actions">
        <button className="is-primary" onClick={save} disabled={!dirty || store.saving}>
          {store.saving ? "저장 중…" : "저장"}
        </button>
        <button className="is-quiet" onClick={reset} disabled={!store.isCustom || store.saving}>
          기본값으로
        </button>
        {draft !== null ? (
          <button className="is-quiet" onClick={() => setDraft(null)} disabled={store.saving}>
            되돌리기
          </button>
        ) : null}
      </div>
      {error ? <p className="prompt-editor-error">{error}</p> : null}
      <details className="prompt-editor-preview">
        <summary>이 강의로 채워 보기</summary>
        <pre>{renderPreviewPrompt(text, detail)}</pre>
      </details>
    </div>
  );
}
