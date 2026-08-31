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
import { ActionCard, PanelGroup, PanelTool, Remake, RemakeConfirm } from "./panelShared";

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
        <ActionCard
          shape="is-key is-download"
          hit={
            <a
              className="panel-action-hit"
              href={storeReady ? EXTENSION_STORE_URL : EXTENSION_DOWNLOAD_URL}
              download={storeReady ? undefined : true}
              target={storeReady ? "_blank" : undefined}
              rel={storeReady ? "noreferrer" : undefined}
            >
              <Body
                name={storeReady ? "Chrome 웹스토어에서 설치" : "예습 브리지 내려받기"}
                note="설치하면 필기와 프롬프트가 자동으로 들어갑니다"
              />
            </a>
          }
        />
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

  /* 기본 링크를 다시 만드는 것은 관리자뿐이다. **그 버튼은 기본 링크 카드
     안에 든다** — 아래 따로 줄을 세우면 무엇이 다시 만들어지는지 글씨로만
     알 수 있었다(2026-08-31 관리자 지시). */
  const sharedTools =
    isAdmin && canMake && detail.preview?.shareUrl ? (
      <Remake
        label="다시 만들기"
        hint="기본 링크 다시 만들기"
        busy={busy === "shared"}
        disabled={Boolean(busy)}
        onClick={() => setAskingRemake(true)}
      />
    ) : null;

  /* 개인 링크 카드에 드는 것. 카드가 무엇을 다시 만드는지를 자리로 말한다. */
  const personalTools =
    hasPersonal && canMake ? (
      // 자기 것이라 묻지 않는다. 옛 대화는 해당 AI 서비스에 그대로 남아 있고
      // 여기서 가리키는 주소만 새것으로 바뀐다.
      <Remake
        label="다시 만들기"
        hint="개인 링크를 새 대화로 다시 만들기"
        busy={busy === "personal"}
        disabled={Boolean(busy)}
        onClick={() => void start("personal")}
      />
    ) : null;

  /* **프롬프트 고치기는 카드 밖, 갈래의 오른쪽 아래에 선다(2026-08-31 관리자
     지시).** 개인 링크에만 듣는 것이라 그 카드 안에 넣어 두었는데, 카드 안은
     그 카드를 여는 자리라 「고치기」가 「열기」와 같은 무게로 붙어 있었다.
     펼쳐지는 편집칸이 바로 아래에 오므로 그 문이 편집칸 옆에 서는 것이 맞다. */
  const promptTool = (
    <div className="panel-aside">
      <PanelTool
        icon="✎"
        label={showPrompt ? "프롬프트 접기" : "프롬프트 수정"}
        hint={`내 예습 프롬프트 ${showPrompt ? "접기" : "고치기"}`}
        active={showPrompt}
        dot={promptStore.isCustom}
        expanded={showPrompt}
        onClick={() => setShowPrompt((open) => !open)}
      />
    </div>
  );

  /* 기본 링크 — 강의당 하나, 반 전체가 같은 것을 읽는다. 문구가 고정이라
     누가 만들었든 같은 것을 물은 대화다. 만드는 것은 관리자뿐이다. */
  const shared = detail.preview?.shareUrl ? (
    <SharedOpen
      url={detail.preview.shareUrl}
      lectureId={lectureId}
      provider={detail.preview.provider}
      tools={sharedTools}
    />
  ) : !canMake ? (
    <ActionCard shape="is-key is-empty" hit={<span className="panel-action-hit"><Body name="기본 링크" note="작년 필기 대기" /></span>} />
  ) : isAdmin ? (
    <ActionCard
      shape="is-key"
      hit={
        <button className="panel-action-hit" onClick={() => start("shared")} disabled={Boolean(busy)}>
          <Body name="기본 링크" note={busy === "shared" ? "여는 중…" : "만들기"} />
        </button>
      }
    />
  ) : (
    <ActionCard shape="is-key is-empty" hit={<span className="panel-action-hit"><Body name="기본 링크" note="아직 없습니다" /></span>} />
  );

  /* 개인 링크 — 사람마다 하나. 프롬프트도 자기 것으로 묻는다. */
  const personal = detail.myPreview?.conversationUrl ? (
    <ActionCard
      shape="is-key"
      hit={
        /* 저장되면 이 자리가 회색 버튼("개인 링크 만들기")에서 색이 든 카드로
           바뀐다. 색이 곧 "내 대화가 저장돼 있다"는 표시다.

           주소는 title에 그대로 둔다 — 빈 AI 창이 뜰 때 무엇이 저장돼 있는지
           볼 데가 여기밖에 없다. */
        <a
          className="panel-action-hit"
          href={detail.myPreview.conversationUrl}
          title={detail.myPreview.conversationUrl}
          target="_blank"
          rel="noreferrer"
        >
          <Body name="개인 링크" />
        </a>
      }
      tools={personalTools}
    />
  ) : canMake ? (
    <ActionCard
      shape="is-key is-faint"
      hit={
        <button className="panel-action-hit" onClick={() => start("personal")} disabled={Boolean(busy)}>
          <Body name="개인 링크" note={busy === "personal" ? "여는 중…" : "만들기"} />
        </button>
      }
      tools={personalTools}
    />
  ) : (
    <ActionCard shape="is-key is-empty" hit={<span className="panel-action-hit"><Body name="개인 링크" note="작년 필기 대기" /></span>} />
  );

  return (
    <PanelGroup tone="preview" title="예습">
      <div className="panel-pair">
        {shared}
        {personal}
      </div>
      {promptTool}

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
      {showPrompt ? (
        <PromptEditor store={promptStore} detail={detail} provider={provider} onProvider={setProvider} />
      ) : null}
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
  tools,
}: {
  url: string;
  lectureId: string;
  provider: PreviewProvider;
  tools?: React.ReactNode;
}) {
  return (
    <ActionCard
      shape="is-key"
      hit={
        <a
          className="panel-action-hit"
          href={url}
          target="_blank"
          rel="noreferrer"
          onClick={() => watchSharedLink(lectureId, provider, url)}
        >
          <Body name="기본 링크" />
        </a>
      }
      tools={tools}
    />
  );
}

/**
 * 카드 안의 한 줄. 이름과, 있으면 그 옆의 값.
 *
 * **부제는 걷어냈다(2026-08-31 관리자 지시 — 「ChatGPT · 공통」 같은 것).** 어느
 * AI인지는 갈래 머리의 고르개가 이미 말하고, 「공통」·「내 대화」는 이름이
 * 「기본」·「개인」으로 이미 말한 것을 되풀이한 것이었다. 남는 것은 값이거나
 * 상태다 — 「만들기」·「아직 없습니다」·「여는 중…」.
 */
function Body({ name, note }: { name: string; note?: string }) {
  return (
    <>
      <strong>{name}</strong>
      {note ? <small>{note}</small> : null}
    </>
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
  provider,
  onProvider,
}: {
  store: ReturnType<typeof usePreviewPrompt>;
  detail: LectureDetail;
  provider: PreviewProvider;
  onProvider: (next: PreviewProvider) => void;
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
      {/* **어느 AI로 물을지도 여기서 고른다(2026-08-31 관리자 지시).** 갈래 머리에
          늘 떠 있던 고르개인데, 한 번 정하면 바꿀 일이 드물어서 자리만 차지했다.

          **이것만은 기본 링크에도 듣는다** — 아래 프롬프트는 개인 링크의 것이다.
          그 갈림을 적어 두지 않으면 여기 있는 것이 다 개인 것으로 읽힌다. */}
      <label className="prompt-editor-model">
        <span>어느 AI로 물을까</span>
        <select
          aria-label="예습에 쓸 AI"
          value={provider}
          onChange={(event) => onProvider(event.target.value as PreviewProvider)}
        >
          {previewProviders.map((item) => <option value={item} key={item}>{previewProviderLabels[item]}</option>)}
        </select>
      </label>

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
