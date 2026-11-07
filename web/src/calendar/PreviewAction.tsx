import { useState, type ReactNode } from "react";
import { ChatSplit } from "./ChatSplit";
import { api } from "../api";
import { notePreviewAction } from "../usage";
import {
  absoluteUrl,
  bumpPreviewVersion,
  extensionCompatible,
  extensionInstalled,
  extensionPossible,
  requestPreview,
  watchSharedLink,
} from "../bridge/previewBridge";
import { ExtensionSetup } from "../bridge/ExtensionSetup";
import { AUTO_SEND_MIN_VERSION } from "../bridge/version";
import {
  renderPreviewPrompt,
} from "../lecture/previewPrompt";
import { PromptEditor } from "./PromptEditor";
import { usePreviewPrompt } from "../lecture/usePreviewPrompt";
import { readSharedPreviewPrompt, useSharedPreviewPrompt } from "../lecture/useSharedPreviewPrompt";
import { previewProviderLabels, previewProviders, type LectureDetail, type LectureRef, type PreviewProvider } from "../types/lectures";
import { useMe } from "../useMe";
import { ActionCard, PanelGroup, PanelTool, RemakeConfirm } from "./panelShared";

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
  trailing,
}: {
  lecture: LectureRef;
  detail: LectureDetail;
  base: string;
  onError: (message: string) => void;
  /** 같은 줄 끝에 붙는 버튼(2026-11 개편: 「예습 퀴즈」). */
  trailing?: ReactNode;
}) {
  const [busy, setBusy] = useState<"shared" | "personal" | "">("");
  const [askingRemake, setAskingRemake] = useState<boolean | null>(null);
  const [showPrompt, setShowPrompt] = useState(false);
  const [showSharedPrompt, setShowSharedPrompt] = useState(false);
  const [showLinks, setShowLinks] = useState(false);
  const [saved, setSaved] = useState("");
  const [provider, setProvider] = useState<PreviewProvider>(() =>
    detail.myPreview?.provider || detail.preview?.provider || "chatgpt"
  );
  const promptStore = usePreviewPrompt();
  const isAdmin = Boolean(useMe()?.isAdmin);
  const sharedPromptStore = useSharedPreviewPrompt(isAdmin);
  const lectureId = `${lecture.subject}/${lecture.runId}`;
  const notesPrev = detail.files.find((file) => file.kind === "notes_prev");

  /* **관리자는 여기서 링크를 손으로 넣고 고친다(2026-09-21 관리자 지시).** 그
     전까지 이 자리는 확장이 만들어 준 것만 받았고, 손으로 넣는 칸은 `/admin` 의
     강의 카드에만 있었다 — 링크 하나를 바로잡으려고 캘린더를 떠나 300편이 선
     화면에서 그 편을 다시 찾아야 했다.

     **확장이 없는 갈래에도 선다.** 손으로 넣는 것은 확장이 하는 일이 아니고,
     확장이 못 서는 기기(폰)야말로 붙여넣기로 고치는 자리다.

     **칸 둘이 카드 둘과 같은 자리를 쓴다** — 기본 링크는 `preview`, 개인 링크는
     `user_preview` 다. 검증도 일감 세우기도 서버의 그 자리에 있다(`LinkEditor`). */
  const hasLink = Boolean(detail.preview?.shareUrl || detail.myPreview?.conversationUrl);
  const linkTool = isAdmin ? (
    <PanelTool
      icon="🔗"
      label={showLinks ? "링크 접기" : hasLink ? "링크 고치기" : "링크 넣기"}
      hint={`예습 링크 ${showLinks ? "접기" : hasLink ? "고치기" : "넣기"} (관리자)`}
      active={showLinks}
      expanded={showLinks}
      onClick={() =>
        setShowLinks((open) => {
          if (!open) setSaved("");
          return !open;
        })
      }
    />
  ) : null;

  const linkEditor =
    isAdmin && showLinks ? (
      <LinkEditor
        lecture={lecture}
        preview={detail.preview}
        myPreview={detail.myPreview}
        onSaved={(note) => {
          setSaved(note);
          setShowLinks(false);
          // 패널이 들고 있는 상세는 이 저장을 모른다. 확장이 밀어 줄 때와 같은
          // 신호로 다시 받아 온다 — 안 그러면 카드가 옛 링크를 그대로 가리킨다.
          bumpPreviewVersion();
        }}
      />
    ) : null;

  /* 저장한 뒤 편집칸은 닫히고 카드가 새 값으로 바뀐다. 그것만으로는 **일감이
     섰는지**가 안 보여서 한 줄을 남긴다 — 기본 링크가 바뀌면 서버가 Pre-Quiz를
     다시 만들 일감을 세운다. */
  const savedNote = saved && !showLinks ? <p className="panel-hint">{saved}</p> : null;
  const sharedPromptTool = isAdmin ? (
    <PanelTool icon="✎" label={showSharedPrompt ? "기본 프롬프트 접기" : "기본 프롬프트 수정"}
      hint="모든 강의의 기본 예습 프롬프트 수정 (관리자)"
      active={showSharedPrompt} expanded={showSharedPrompt}
      onClick={() => setShowSharedPrompt((open) => !open)} />
  ) : null;
  const sharedPromptEditor = isAdmin && showSharedPrompt ? (
    <PromptEditor store={sharedPromptStore} detail={detail} provider={provider} onProvider={setProvider} shared />
  ) : null;

  /**
   * 확장이 자료를 첨부하고 프롬프트를 채운다. 여기서는 어느 자료를 어느 강의로,
   * 어느 몫으로 여는지만 넘긴다 — 서명 URL은 수명이 짧아 누른 순간에 받는다.
   */
  async function start(mode: "shared" | "personal", autoSend: boolean) {
    if (!notesPrev) return;
    if (detail.previewSource?.attachmentNeedsReview) {
      onError("선택한 예습 필기가 아직 준비되지 않았습니다. 자료 갱신 후 다시 시작하세요.");
      return;
    }
    setBusy(mode);
    if (mode === "personal") notePreviewAction(base, "create");
    try {
      const template = mode === "shared" ? await readSharedPreviewPrompt() : promptStore.template;
      const sources = [notesPrev, ...detail.files.filter((file) => file.kind === "jokbo")];
      const files = await Promise.all(sources.map(async (file) => {
        const { url } = await api<{ url: string }>(`${base}/files/${file.id}?purpose=preview_attach`);
        return { id: file.id, filename: file.filename, downloadUrl: absoluteUrl(url), contentType: file.contentType };
      }));
      await requestPreview({
        requestId: `${lecture.runId}-${performance.now()}`,
        lectureId,
        provider,
        mode,
        prompt: renderPreviewPrompt(template, detail),
        files,
        autoSend,
      });
    } catch (cause) {
      onError((cause as Error).message);
    } finally {
      setBusy("");
    }
  }

  /* 확장이 없으면 새로 **만들** 수는 없다. 다만 이미 있는 링크는 그냥 주소라
     확장 없이도 열린다 — 기본 링크도, 컴퓨터에서 만들어 둔 개인 링크도.

     전에는 이 갈래가 기본 링크만 보여 주고 개인 링크는 통째로 감췄다. **모바일
     브라우저에는 크롬 확장이 아예 없으므로 폰에서는 내 대화를 여는 길이 하나도
     없었다**(2026-09-18 관리자 지시). 저장은 서버에 돼 있는데 화면이 안 꺼내
     줬을 뿐이다.

     그래서 둘을 나란히 세우는 것은 위와 같고, 다른 것은 만들기 자리에 무엇이
     서느냐뿐이다 — 설치 안내이거나, 설치조차 못 하는 기기면 한 줄짜리 설명이다. */
  if (!extensionInstalled()) {
    const canInstall = extensionPossible();
    return (
      <PanelGroup tone="preview" title="예습" note="강의 전에 읽는 대화">
        <div className="panel-pair">
          {detail.preview?.shareUrl ? (
            <SharedOpen
              url={detail.preview.shareUrl}
              lectureId={lectureId}
              base={base}
              provider={detail.preview.provider}
            />
          ) : (
            <Empty name="공통 대화" note="아직 없습니다" />
          )}
          {detail.myPreview?.conversationUrl ? (
            <ChatSplit tone="pre" main={<PersonalLink url={detail.myPreview.conversationUrl} base={base} />}
              onPrompt={() => setShowPrompt(open => !open)} promptOpen={showPrompt} promptCustom={promptStore.isCustom} />
          ) : (
            <Empty name="개인 대화" note={canInstall ? "확장을 설치하면 만듭니다" : "컴퓨터에서 만듭니다"} />
          )}
          {trailing}
        </div>
        {linkTool || sharedPromptTool ? <div className="panel-aside">{linkTool}{sharedPromptTool}</div> : null}
        {sharedPromptEditor}
        {linkEditor}
        {savedNote}
        {canInstall ? (
          <ExtensionSetup />
        ) : (
          /* 설치 단추를 못 누르는 기기에 설치 카드를 세우지 않는다. 대신 왜 만들기가
             여기 없는지를 한 줄로 적는다 — 없는 이유를 안 적으면 「고장」으로 읽힌다. */
          <p className="panel-steps">
            예습 대화를 <b>만드는</b> 것은 크롬 확장이 하고, 확장은 컴퓨터에만 설치됩니다.
            여기서는 컴퓨터에서 만들어 둔 링크를 엽니다.
          </p>
        )}
      </PanelGroup>
    );
  }

  // 작년 필기가 없으면 새로 만들 수는 없다. 다만 이미 만들어진 링크는 그대로
  // 열려야 하므로 여기서 통째로 돌려보내지 않는다.
  const canMake = Boolean(notesPrev) && !detail.previewSource?.attachmentNeedsReview;
  const compatible = extensionCompatible();
  const automatic = extensionCompatible(AUTO_SEND_MIN_VERSION);
  const sharedTools = canMake && isAdmin ? (
    <PanelTool icon="↗" label={automatic ? "자동전송" : "직접전송"}
      hint={automatic ? "기본 링크 생성 · 첨부 후 자동 전송 (관리자)" : "기본 링크 생성 · 첨부 후 직접 전송 (관리자)"}
      disabled={Boolean(busy) || !compatible}
      onClick={() => {
        if (detail.preview?.shareUrl) setAskingRemake(automatic);
        else void start("shared", automatic);
      }} />
  ) : null;

  /* **프롬프트 고치기는 카드 밖, 갈래의 오른쪽 아래에 선다(2026-08-31 관리자
     지시).** 개인 링크에만 듣는 것이라 그 카드 안에 넣어 두었는데, 카드 안은
     그 카드를 여는 자리라 「고치기」가 「열기」와 같은 무게로 붙어 있었다.
     펼쳐지는 편집칸이 바로 아래에 오므로 그 문이 편집칸 옆에 서는 것이 맞다.

     **줄 자체는 이제 둘이 같이 쓴다** — 관리자의 「링크 고치기」가 왼쪽에
     선다(2026-09-21). 둘 다 이 갈래의 것이지 어느 카드 하나의 것이 아니다. */

  /* 기본 링크는 강의당 하나다. 관리자들이 저장한 공통 문구로 새 대화를 만든다. */
  const shared = detail.preview?.shareUrl ? (
    <SharedOpen
      url={detail.preview.shareUrl}
      lectureId={lectureId}
      base={base}
      provider={detail.preview.provider}
      tools={sharedTools}
    />
  ) : !canMake ? (
    <Empty name="공통 대화" note="예습 필기 대기" />
  ) : isAdmin ? (
    <ActionCard
      shape="is-key"
      hit={
        <button type="button" className="panel-action-hit" aria-label="공통 대화 만들기" disabled={Boolean(busy) || !compatible} onClick={() => void start("shared", false)}>
          <Body name="공통 대화" note={busy === "shared" ? "여는 중…" : "만들기"} />
        </button>
      }
      tools={sharedTools}
    />
  ) : (
    <Empty name="공통 대화" note="아직 없습니다" />
  );

  /* 개인 링크 — 사람마다 하나. 프롬프트도 자기 것으로 묻는다. */
  /* 개인 대화 — C안(2026-11-07): 왼쪽은 처음엔 만들기(＋), 그 뒤엔 열기(↗). ▾에 새 대화 만들기·내 프롬프트 수정. */
  const makeDisabled = Boolean(busy) || !compatible || !promptStore.loaded;
  const personal = detail.myPreview?.conversationUrl ? (
    <ChatSplit tone="pre" main={<PersonalLink url={detail.myPreview.conversationUrl} base={base} />}
      onRemake={canMake ? () => void start("personal", false) : undefined} remakeDisabled={makeDisabled}
      onPrompt={() => setShowPrompt(open => !open)} promptOpen={showPrompt} promptCustom={promptStore.isCustom} />
  ) : canMake ? (
    <ChatSplit tone="pre"
      main={
        <button type="button" className="chat-split-main" aria-label="개인 대화 만들기" disabled={makeDisabled}
          onClick={() => void start("personal", false)}>
          <span aria-hidden="true">＋</span>{busy === "personal" ? "여는 중…" : "개인 대화"}
        </button>
      }
      onPrompt={() => setShowPrompt(open => !open)} promptOpen={showPrompt} promptCustom={promptStore.isCustom} />
  ) : (
    <Empty name="개인 대화" note="예습 필기 대기" />
  );

  return (
    <PanelGroup tone="preview" title="예습">
      <div className="panel-pair">
        {shared}
        {personal}
        {trailing}
      </div>
      <div className="panel-aside">
        {linkTool}
        {sharedPromptTool}
      </div>
      {linkEditor}
      {savedNote}
      {sharedPromptEditor}

      {canMake ? <ExtensionSetup /> : null}

      {askingRemake !== null ? (
        <RemakeConfirm
          message="모두가 보는 링크가 새 대화로 바뀝니다. 옛 링크는 기존 AI 서비스에 그대로 남지만 여기서는 안 보입니다."
          onConfirm={() => {
            const autoSend = askingRemake;
            setAskingRemake(null);
            void start("shared", autoSend);
          }}
          onCancel={() => setAskingRemake(null)}
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
/**
 * 눌렀다고 서버에 한 줄 남긴다.
 *
 * **주소가 서버를 안 지나기 때문이다.** 기본 링크도 개인 링크도 AI 서비스의
 * 주소라, 누르면 그 길로 가고 우리 서버는 아무것도 못 본다 — 그래서 누르는 자리가
 * 알려 준다(2026-09-19 관리자 질문: 「기본링크도 얼마나 클릭했는지 알 수는 없나?」).
 *
 * **기다리지 않는다.** 링크는 그 자리에서 열려야 하고, 이 한 줄이 실패했다고
 * 열리지 않으면 바꿔치기가 나쁜 쪽이다. 그래서 `void` 로 띄워 보내고 오류도 삼킨다.
 */

function SharedOpen({
  url,
  lectureId,
  base,
  provider,
  tools,
}: {
  url: string;
  lectureId: string;
  base: string;
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
          onClick={() => {
            watchSharedLink(lectureId, provider, url);
            notePreviewAction(base, "share");
          }}
        >
          <Body name="공통 대화" />
        </a>
      }
      tools={tools}
    />
  );
}

/**
 * 개인 링크 열기. **확장이 있든 없든 같은 카드다.**
 *
 * 저장돼 있으면 이 자리가 회색 버튼("만들기")에서 색이 든 카드로 바뀐다. 색이
 * 곧 "내 대화가 저장돼 있다"는 표시다.
 *
 * 주소는 title에 그대로 둔다 — 빈 AI 창이 뜰 때 무엇이 저장돼 있는지 볼 데가
 * 여기밖에 없다.
 *
 * **여는 데는 확장이 필요 없다.** `conversationUrl` 은 그 AI 서비스의 내 대화
 * 주소라 로그인만 돼 있으면 폰에서도 열린다. 확장이 없는 갈래가 이 카드를 같이
 * 쓰는 이유다.
 */
/** 개인 대화 열기(↗). ChatSplit의 왼쪽 칸. */
function PersonalLink({ url, base }: { url: string; base: string }) {
  return (
    <a className="chat-split-main" href={url} title={url} target="_blank" rel="noreferrer"
      onClick={() => notePreviewAction(base, "mine")}>
      <span aria-hidden="true">↗</span>개인 대화
    </a>
  );
}


/** 아직 없는 링크 자리. 칸은 그대로 서고 왜 없는지만 적는다. */
function Empty({ name, note }: { name: string; note: string }) {
  return (
    <ActionCard
      shape="is-key is-empty"
      hit={<span className="panel-action-hit"><Body name={name} note={note} /></span>}
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
 * 위의 카드 둘을 손으로 넣고 고치는 칸. **관리자만 본다.**
 *
 * 확장이 만들어 주는 길(`start(...)`)과 **하는 일이 다르다.** 저쪽은 대화를 새로
 * 열어 만드는 것이고 여기는 **이미 있는 주소를 붙여넣는 것**이다. 남이 만든
 * 대화를 반의 기본 링크로 세우거나, 잘못 저장된 주소를 바로잡거나, 비워서
 * 지우는 자리다.
 *
 * **칸 둘이 카드 둘과 1:1 이고, 그래서 쓰는 길도 둘이다.**
 *
 *     기본 링크   preview        PUT /api/admin/lectures/…/preview
 *     개인 링크   user_preview   PUT /api/lectures/…/my-preview
 *
 * **처음에는 두 번째 칸이 `preview.conversation_url` 을 썼고, 그것이 틀렸다**
 * (2026-09-21 관리자 — 「관리자 개인링크가 안 나타나는데?」). 그 값은 「기본
 * 링크를 누가 만들었나」의 흔적이라 패널의 어느 카드도 안 읽는다. 로컬에서 넣어
 * 보니 저장은 되는데 화면에는 아무 데도 안 나왔다 — 개인 링크 카드가 읽는 것은
 * `user_preview` 이고, 그것은 사람마다 다른 자리다. `/admin` 의 그 칸은 흔적을
 * 고치는 것이라 그대로 둔다.
 *
 * 주소 꼴을 재는 것도, 기본 링크가 바뀌었을 때 Pre-Quiz 일감을 세우는 것도
 * 서버의 그 두 자리에 있고 여기서 되풀이하지 않는다.
 *
 * `my-preview` 에는 관리자 문이 없다 — 자기 것이라서다. 여기서만 관리자에게
 * 보이는 이유는 이 칸이 **기본 링크와 같이 서기 때문**이지 개인 링크가 관리자
 * 것이라서가 아니다.
 */
function LinkEditor({
  lecture,
  preview,
  myPreview,
  onSaved,
}: {
  lecture: LectureRef;
  preview: LectureDetail["preview"];
  myPreview: LectureDetail["myPreview"];
  /** 저장이 끝났다. 무엇이 됐는지 한 줄로 알린다. */
  onSaved: (note: string) => void;
}) {
  const [provider, setProvider] = useState<PreviewProvider>(
    preview?.provider ?? myPreview?.provider ?? "chatgpt",
  );
  const [share, setShare] = useState(preview?.shareUrl ?? "");
  const [mine, setMine] = useState(myPreview?.conversationUrl ?? "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const path = `${encodeURIComponent(lecture.subject)}/${encodeURIComponent(lecture.runId)}`;
  /* **바뀐 것만 보낸다.** 기본 링크는 같은 주소를 되밀어도 서버가 일감을 안
     세우지만, 개인 링크까지 늘 같이 보내면 안 건드린 칸이 제공자 바뀜에 휩쓸린다.
     제공자는 두 주소에 다 걸리므로 그것이 바뀌어도 그 칸은 다시 쓴다. */
  const sharedDirty =
    share.trim() !== (preview?.shareUrl ?? "") || (Boolean(preview) && provider !== preview?.provider);
  const mineDirty =
    mine.trim() !== (myPreview?.conversationUrl ?? "") ||
    (Boolean(myPreview) && provider !== myPreview?.provider);

  async function save() {
    setSaving(true);
    setError("");
    const done: string[] = [];
    try {
      if (sharedDirty) {
        const result = await api<{ shareUrl: string; queued: unknown }>(
          `/api/admin/lectures/${path}/preview`,
          { method: "PUT", body: JSON.stringify({ provider, shareUrl: share.trim() }) },
        );
        done.push(
          !result.shareUrl
            ? "기본 링크를 지웠습니다"
            : result.queued
              ? "기본 링크를 저장했습니다 · Pre-Quiz를 만들 일감이 섰습니다"
              : "기본 링크를 저장했습니다",
        );
      }
      if (mineDirty) {
        const result = await api<{ conversationUrl: string }>(`/api/lectures/${path}/my-preview`, {
          method: "PUT",
          body: JSON.stringify({ provider, conversationUrl: mine.trim() }),
        });
        done.push(result.conversationUrl ? "개인 링크를 저장했습니다" : "개인 링크를 지웠습니다");
      }
      onSaved(done.length ? `${done.join(" · ")}.` : "바뀐 것이 없습니다.");
    } catch (cause) {
      setError((cause as Error).message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="link-editor">
      {/* 어느 AI의 주소인가. 고르는 것이 아니라 **재는 잣대다** — 서버가 이것으로
          주소 꼴을 맞춰 보고, 틀리면 422로 돌려보낸다. 위 프롬프트 편집칸의
          고르개("어느 AI로 물을까")는 앞으로 만들 것을 정하는 자리라 다르다. */}
      <label className="link-editor-model">
        <span>어느 AI의 링크인가</span>
        <select
          aria-label="기본 링크의 AI"
          value={provider}
          onChange={(event) => setProvider(event.target.value as PreviewProvider)}
        >
          {previewProviders.map((item) => (
            <option value={item} key={item}>
              {previewProviderLabels[item]}
            </option>
          ))}
        </select>
      </label>

      <label className="link-editor-field">
        <span>기본 링크 — 반 전체가 읽는다</span>
        <input
          value={share}
          placeholder="공개 공유 주소"
          spellCheck={false}
          onChange={(event) => setShare(event.target.value)}
        />
      </label>

      {/* **위 칸의 개인 링크 카드가 여는 바로 그 주소다.** 처음에는 여기가
          `preview.conversation_url`(「기본 링크를 누가 만들었나」의 흔적)을
          썼는데, 그 값은 패널 어디에도 안 나온다 — 넣어 보고 확인했다. 카드가
          읽는 것은 `user_preview` 이고 그것은 사람마다 다르다. */}
      <label className="link-editor-field">
        <span>개인 링크 — 나만 연다</span>
        <input
          value={mine}
          placeholder="개인 대화 주소"
          spellCheck={false}
          onChange={(event) => setMine(event.target.value)}
        />
      </label>

      <div className="link-editor-actions">
        <button className="is-primary" onClick={save} disabled={saving}>
          {saving ? "저장 중…" : "저장"}
        </button>
        <small>비우고 저장하면 지워집니다.</small>
      </div>
      {error ? <p className="prompt-editor-error">{error}</p> : null}
    </div>
  );
}
