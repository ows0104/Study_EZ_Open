import { useCallback, useEffect, useRef, useState } from "react";
import { api, downloadSignedFile, openSignedFile } from "../api";
import {
  previewProviderLabels,
  previewProviders,
  type DeckKind,
  type LectureDetail,
  type LectureFile,
  type LectureRef,
  type PreviewProvider,
  type PrequizJob,
  type RunnerBeat,
} from "../types";
import {
  absoluteUrl,
  bumpPreviewVersion,
  extensionInstalled,
  requestPreview,
  usePreviewVersion,
  watchSharedLink,
} from "../bridge/previewBridge";
import { EXTENSION_DOWNLOAD_URL, EXTENSION_STORE_URL } from "../bridge/protocol";
import { PROMPT_TOKENS, renderPreviewPrompt, SHARED_PREVIEW_PROMPT } from "../lecture/previewPrompt";
import { usePreviewPrompt } from "../lecture/usePreviewPrompt";
import { lectureHref, prequizHref, prequizWindow } from "../links";
import { useMe } from "../useMe";
import { categoryLabel, type CalendarEntry } from "./entries";

/**
 * 칸 하나를 눌렀을 때 옆에 서는 패널.
 *
 * **어느 칸을 눌러도 열린다.** 전에는 강의 자료가 붙은 칸만 링크였는데, 시간표
 * 369칸 중 자료가 붙은 것이 여덟이라 화면의 거의 전부가 눌러도 아무 말이 없는
 * 상태였다. "아직 없다"는 것도 대답이므로 여기서 말한다.
 *
 * 캘린더를 덮지 않고 옆으로 민다. 자료를 여닫는 동안 어느 주를 보고 있었는지
 * 잃지 않는다는 뜻이고, 다른 칸을 바로 눌러 갈아탈 수 있다는 뜻이기도 하다.
 * 좁은 화면에서만 아래에서 올라오는 시트가 된다 — 옆에 설 자리가 없어서다.
 *
 * **위에서부터 할 일, 그 아래가 정보다.** 강의 정보는 열어 볼 일이 드물어서
 * 맨 아래로 내렸다.
 */
export function EventPanel({ entry, onClose }: { entry: CalendarEntry; onClose: () => void }) {
  const panel = useRef<HTMLElement>(null);
  const [chosen, setChosen] = useState(0);
  const lecture: LectureRef | undefined = entry.lectures[chosen];
  const { detail, error } = useLectureDetail(lecture);

  useEffect(() => {
    // 패널을 연 것이 키보드일 수 있다. 초점을 안 옮기면 다음 Tab이 패널이 아니라
    // 남은 칸들로 흘러간다. 닫을 때는 누른 칸으로 돌려준다.
    const restore = document.activeElement as HTMLElement | null;
    panel.current?.focus({ preventScroll: true });
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("keydown", onKey);
      restore?.focus?.({ preventScroll: true });
    };
  }, [onClose]);

  const primary = entry.detail || entry.title;
  const hasSeries = Boolean(entry.detail && entry.title && entry.detail !== entry.title);

  return (
    <>
      {/* 좁은 화면에서만 보인다. 넓은 화면에서는 패널이 캘린더를 덮지 않으므로
          가릴 것도, 눌러서 닫을 것도 없다. */}
      <div className="panel-scrim" onClick={onClose} aria-hidden="true" />
      <aside className="event-panel" aria-label={primary} tabIndex={-1} ref={panel}>
        <header className="event-panel-head">
          <span className={`event-panel-kind is-${entry.category}`}>{categoryLabel(entry.category)}</span>
          <button className="is-quiet event-panel-close" onClick={onClose} aria-label="닫기">
            ✕
          </button>
        </header>

        <h2 className="event-panel-title">{primary}</h2>

        {/* 한 교시에 여러 강의가 열릴 때(선택형 과목). 자동으로 하나를 고르면
            다른 강의가 화면에서 사라지므로 고르게 한다. */}
        {entry.lectures.length > 1 ? (
          <div className="event-panel-switch" role="group" aria-label="강의 고르기">
            {entry.lectures.map((option, index) => (
              <button
                key={option.runId}
                className={index === chosen ? "is-selected" : ""}
                aria-pressed={index === chosen}
                onClick={() => setChosen(index)}
              >
                {option.title}
              </button>
            ))}
          </div>
        ) : null}

        {error ? <p className="notice is-error">{error}</p> : null}

        {lecture ? (
          detail ? (
            <KeyActions lecture={lecture} detail={detail} />
          ) : error ? null : (
            <p className="event-panel-loading">자료를 불러오는 중…</p>
          )
        ) : (
          /* 없다는 것을 말하는 자리다. 이것이 없으면 "아직 안 올라옴"과
             "눌러도 안 되는 화면"을 구분할 수 없다. */
          <p className="event-panel-empty">
            아직 올라온 자료가 없습니다.
            <small>예습·퀴즈가 준비되면 이 칸에 점이 붙습니다.</small>
          </p>
        )}

        {/* 여기부터는 읽을 것이지 누를 것이 아니다. */}
        <dl className="event-panel-facts">
          <Fact label="일시">
            <time>
              {entry.date} · {entry.startTime}–{entry.endTime}
            </time>
          </Fact>
          {entry.professor ? <Fact label="담당">{entry.professor}</Fact> : null}
          {entry.course ? <Fact label="과목">{entry.course}</Fact> : null}
          {hasSeries ? <Fact label="교시명">{entry.title}</Fact> : null}
          {/* 필기 파일 자체는 위로 올라갔다. 여기 남는 것은 누가 썼는가뿐이다. */}
          {detail?.author ? (
            <Fact label="필기자">
              {detail.author}
              {detail.version ? ` v${detail.version}` : ""}
            </Fact>
          ) : null}
        </dl>

        {lecture ? (
          <a className="event-panel-more" href={lectureHref(lecture)} target="_blank" rel="noreferrer">
            강의 화면 전체 보기 →
          </a>
        ) : null}
      </aside>
    </>
  );
}

/**
 * 강의 상세를 불러온다. 고른 강의가 바뀔 때, 그리고 예습 링크가 저장될 때.
 *
 * 링크는 화면 밖에서 온다 — 다른 탭에서 대화가 끝나면 확장이 밀어 준다. 그래서
 * 강의만 보고 있으면 저장된 것을 영영 못 본다.
 */
function useLectureDetail(lecture: LectureRef | undefined) {
  const [detail, setDetail] = useState<LectureDetail | null>(null);
  const [error, setError] = useState("");
  const key = lecture ? `${lecture.subject}/${lecture.runId}` : "";
  const version = usePreviewVersion();

  useEffect(() => {
    if (!lecture) return;
    let live = true;
    // 링크가 저장돼 다시 부르는 경우에는 비우지 않는다. 화면이 깜빡이고, 그
    // 사이에 버튼이 사라졌다 나타난다.
    setError("");
    api<LectureDetail>(`/api/lectures/${encodeURIComponent(lecture.subject)}/${encodeURIComponent(lecture.runId)}`)
      .then((next) => live && setDetail(next))
      .catch((cause: Error) => live && setError(cause.message));
    return () => {
      live = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, version]);

  // 강의가 바뀌면 앞 강의의 값을 잠깐이라도 보여 주지 않는다.
  useEffect(() => {
    setDetail(null);
  }, [key]);

  return { detail, error };
}

function Fact({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="event-panel-fact">
      <dt>{label}</dt>
      <dd>{children}</dd>
    </div>
  );
}

/**
 * 강조하는 셋. 예습 링크 · Pre-Quiz · Main-Quiz 덱.
 *
 * 링크는 누르면 바로 열리고 덱은 누르면 바로 받는다. 중간에 확인할 화면을
 * 두지 않는다 — 그 셋이 이 패널의 존재 이유다.
 *
 * **필기는 그 셋이 아니다.** 한동안 여기 큰 버튼으로 세워 뒀는데 주요 버튼만큼
 * 눈에 걸렸다. 아래 조용한 줄로 돌려보내되, 누르면 열리는 것은 그대로 둔다.
 */
function KeyActions({ lecture, detail }: { lecture: LectureRef; detail: LectureDetail }) {
  const base = `/api/lectures/${encodeURIComponent(lecture.subject)}/${encodeURIComponent(lecture.runId)}`;
  const [error, setError] = useState("");
  const fileOf = (kind: LectureFile["kind"]) => detail.files.find((file) => file.kind === kind);
  const quiz = detail.prequiz;

  async function download(file: LectureFile) {
    try {
      await downloadSignedFile(`${base}/files/${file.id}`, file.filename);
    } catch (cause) {
      setError((cause as Error).message);
    }
  }

  // `inline=1`이 없으면 서버가 첨부로 서명해 준다. 그러면 새 탭이 뜨자마자
  // 내려받기로 바뀌고 빈 탭만 남는다.
  async function open(file: LectureFile) {
    try {
      await openSignedFile(`${base}/files/${file.id}?inline=1`);
    } catch (cause) {
      setError((cause as Error).message);
    }
  }

  return (
    <div className="event-panel-actions">
      <PreviewAction lecture={lecture} detail={detail} base={base} onError={setError} />

      {/* 누르면 Pre-Quiz 전용 창이 열린다 — 캘린더도 이 패널도 그대로 남는다.
          전에는 강의 화면으로 보내 놓고 거기서 다시 누르게 했다.

          **덱이 기본이던 것을 뒤집었다(2026-08-23 관리자 지시).** 덱은 그 아래
          줄에서 받는다 — Anki를 깐 자리에서 반복할 사람의 것이다. */}
      {quiz ? (
        <a className="panel-action is-key" href={prequizHref(lecture)} target={prequizWindow(lecture)}>
          <strong>Pre-Quiz</strong>
          <small>
            {quiz.itemCount}장
            {quiz.answered ? ` · ${quiz.answered}장 풀었습니다` : " · 웹에서 풉니다"}
          </small>
        </a>
      ) : null}
      {/* 웹 풀이가 있으면 덱은 한 단 낮게 눕는다. 없으면 이 줄이 그 자리를 진다 —
          아직 안 올라온 강의에서 "아직 없습니다"를 말하는 것도 이 줄이다. */}
      {/* 문항 수는 위 줄이 말한다. 여기서 되풀이하면 덱의 장수처럼 읽히는데,
          덱에는 그림 카드까지 들어 있어 언제나 더 많다. */}
      <DeckSlot
        kind="pre"
        label="Pre-Quiz 덱"
        file={fileOf("pre_apkg")}
        lecture={lecture}
        onDownload={download}
        quiet={Boolean(quiz)}
      />

      <DeckSlot
        kind="main"
        label="Main-Quiz 덱"
        file={fileOf("main_apkg")}
        lecture={lecture}
        onDownload={download}
      />

      {/* 강의 정보(일시·담당·과목) 바로 위. 읽는 것에 가깝지만 누르면 열린다. */}
      <Notes detail={detail} onOpen={open} />

      {error ? <p className="notice is-error">{error}</p> : null}
    </div>
  );
}

/**
 * 필기 둘. 작년 것과 올해 것.
 *
 * **누르면 새 탭에서 열린다. 받지 않는다.** PDF라 브라우저가 그대로 보여 줄 수
 * 있다.
 *
 * 생김새는 정보 줄에 가깝다 — 예습 링크·덱과 같은 무게로 세우면 이 패널이
 * 무엇을 하라는 화면인지 흐려진다. 이름은 한 줄로 자르고 전체는 `title`에
 * 남긴다. 어차피 열어 보면 무엇인지 보인다.
 */
function Notes({ detail, onOpen }: { detail: LectureDetail; onOpen: (file: LectureFile) => void }) {
  const rows: [string, LectureFile | undefined][] = [
    ["작년", detail.files.find((file) => file.kind === "notes_prev")],
    ["올해", detail.files.find((file) => file.kind === "notes_current")],
  ];
  return (
    <ul className="event-panel-notes">
      {rows.map(([label, file]) => (
        <li key={label}>
          {file ? (
            <button className="event-panel-note" onClick={() => onOpen(file)} title={`${file.filename} — 새 탭에서 열기`}>
              <span>{label}</span>
              <b>{file.filename}</b>
              <small>{fileSize(file.sizeBytes)}</small>
            </button>
          ) : (
            // 빠지면 "아직 없다"와 "이 강의에는 원래 없다"가 안 갈린다.
            <span className="event-panel-note is-empty">
              <span>{label}</span>
              <b>아직 없음</b>
            </span>
          )}
        </li>
      ))}
    </ul>
  );
}

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
 */
function PreviewAction({
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
  // 토글은 개인 링크 줄 안에 들어가고, 편집칸은 그 줄 아래에 펼쳐진다.
  const promptToggle = (
    <PromptToggle open={showPrompt} custom={promptStore.isCustom} onClick={() => setShowPrompt((o) => !o)} />
  );

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
      <>
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
      </>
    );
  }

  // 작년 필기가 없으면 새로 만들 수는 없다. 다만 이미 만들어진 링크는 그대로
  // 열려야 하므로 여기서 통째로 돌려보내지 않는다.
  const canMake = Boolean(notesPrev);

  return (
    <>
      <label className="preview-provider-select">
        <span>예습 AI</span>
        <select value={provider} onChange={(event) => setProvider(event.target.value as PreviewProvider)}>
          {previewProviders.map((item) => <option value={item} key={item}>{previewProviderLabels[item]}</option>)}
        </select>
      </label>
      {/* 기본 링크 — 강의당 하나, 반 전체가 같은 것을 읽는다. 문구가 고정이라
          누가 만들었든 같은 것을 물은 대화다. 만드는 것은 관리자뿐이다. */}
      {detail.preview?.shareUrl ? (
        <>
          <div className="panel-row">
            <SharedOpen url={detail.preview.shareUrl} lectureId={lectureId} provider={detail.preview.provider} />
            {isAdmin && canMake ? (
              <Remake
                label="기본 링크 다시 만들기"
                busy={busy === "shared"}
                disabled={Boolean(busy)}
                onClick={() => setAskingRemake(true)}
              />
            ) : null}
          </div>
          {askingRemake ? (
            <RemakeConfirm
              message={`모두가 보는 링크가 새 대화로 바뀝니다. 옛 링크는 기존 AI 서비스에 그대로 남지만 여기서는 안 보입니다.`}
              onConfirm={() => {
                setAskingRemake(false);
                void start("shared");
              }}
              onCancel={() => setAskingRemake(false)}
            />
          ) : null}
        </>
      ) : !canMake ? (
        <span className="panel-action is-key is-empty">기본 링크 — 작년 필기가 올라오면 만들 수 있습니다</span>
      ) : isAdmin ? (
        <button className="panel-action is-key" onClick={() => start("shared")} disabled={Boolean(busy)}>
          <strong>{busy === "shared" ? "여는 중…" : "기본 링크 만들기"}</strong>
          <small>{previewProviderLabels[provider]}에서 묻고, 만들어진 공유 링크를 모두에게 냅니다</small>
        </button>
      ) : (
        <span className="panel-action is-key is-empty">기본 링크 — 아직 없습니다</span>
      )}

      {/* 개인 링크 — 사람마다 하나. 프롬프트도 자기 것으로 묻는다. 그래서
          프롬프트 고치기가 이 줄 안에 붙어 있다 — 기본 링크에는 안 듣는다. */}
      {detail.myPreview?.conversationUrl ? (
        <div className="panel-row">
          {/* 저장되면 이 자리가 회색 버튼("개인 예습 시작")에서 이 파란 줄로
              바뀐다. 색이 곧 "내 대화가 저장돼 있다"는 표시다.

              주소는 title에 그대로 둔다 — 빈 AI 창이 뜰 때 무엇이 저장돼
              있는지 볼 데가 여기밖에 없다. */}
          <a
            className="panel-action is-key"
            href={detail.myPreview.conversationUrl}
            title={detail.myPreview.conversationUrl}
            target="_blank"
            rel="noreferrer"
          >
            <strong>개인 링크 · {previewProviderLabels[detail.myPreview.provider]}</strong>
            <small>내 예습 대화 이어서 열기</small>
          </a>
          {promptToggle}
          {canMake ? (
            // 자기 것이라 묻지 않는다. 옛 대화는 해당 AI 서비스에 그대로 남아 있고
            // 여기서 가리키는 주소만 새것으로 바뀐다.
            <Remake
              label="새 대화로 다시 시작"
              busy={busy === "personal"}
              disabled={Boolean(busy)}
              onClick={() => void start("personal")}
            />
          ) : null}
        </div>
      ) : canMake ? (
        <div className="panel-row">
          <button className="panel-action" onClick={() => start("personal")} disabled={Boolean(busy)}>
            <strong>{busy === "personal" ? "여는 중…" : "개인 예습 시작"}</strong>
            <small>{previewProviderLabels[provider]}에서 내 프롬프트로 새 대화를 엽니다</small>
          </button>
          {promptToggle}
        </div>
      ) : null}
      {showPrompt ? <PromptEditor store={promptStore} detail={detail} /> : null}
    </>
  );
}

/**
 * 프롬프트 고치기. 개인 링크 줄 안에 붙는 아이콘 하나다.
 *
 * 전에는 링크 아래 한 줄을 통째로 쓰고 있었는데, 그러면 기본 링크에도 걸리는
 * 말처럼 보인다. 고쳐 쓰는 것은 개인 링크뿐이다.
 *
 * 이름이 화면에 안 나오므로 `aria-label`과 `title`이 그것을 대신한다.
 * 고쳐 쓴 사람에게는 색으로 표시한다 — 안 고친 사람에게는 아무 표시도 없다.
 */
function PromptToggle({ open, custom, onClick }: { open: boolean; custom: boolean; onClick: () => void }) {
  const label = `내 프롬프트 ${open ? "접기" : "고치기"}${custom ? " (고쳐 쓴 것이 있습니다)" : ""}`;
  return (
    <button
      className={`panel-remake panel-prompt${custom ? " is-custom" : ""}${open ? " is-open" : ""}`}
      onClick={onClick}
      aria-label={label}
      aria-expanded={open}
      title={label}
    >
      <span aria-hidden="true">✎</span>
    </button>
  );
}

/**
 * 다시 만들기.
 *
 * 링크를 여는 것에 견주면 드물게 하는 일이라 아이콘 하나로 줄여 링크 옆에
 * 붙인다. 아래에 한 줄로 두면 그 줄이 링크만큼 눈에 걸린다.
 *
 * 이름이 화면에 안 나오므로 `aria-label`과 `title`이 그것을 대신한다 — 아이콘
 * 하나만으로는 무엇이 다시 만들어지는지 알 수 없다.
 */
function Remake({
  label,
  busy,
  busyLabel = "여는 중…",
  disabled,
  onClick,
}: {
  label: string;
  busy: boolean;
  /** 도는 동안 읽어 주는 말. 링크는 「여는 중」이고 덱은 「만드는 중」이다. */
  busyLabel?: string;
  disabled: boolean;
  onClick: () => void;
}) {
  return (
    <button
      className={busy ? "panel-remake is-busy" : "panel-remake"}
      onClick={onClick}
      disabled={disabled}
      aria-label={busy ? busyLabel : label}
      aria-busy={busy}
      title={label}
    >
      <span aria-hidden="true">⟳</span>
    </button>
  );
}

/**
 * 되돌리기 어려운 것을 다시 만들기 전에 한 번 묻는다.
 *
 * 기본 링크는 반 전체가 보는 값이고, Pre-Quiz 덱은 한 편에 15분과 빈 세션 넷이
 * 든다. 둘 다 눌러 버린 뒤에 무르는 길이 없다.
 *
 * `window.confirm` 대신 자리에서 묻는다 — 새 탭을 여는 흐름이라 모달이 팝업
 * 차단과 얽히고, 무엇을 바꾸는지 문장으로 적을 자리도 없다.
 */
function RemakeConfirm({
  message,
  confirm = "바꾸기",
  onConfirm,
  onCancel,
}: {
  message: string;
  confirm?: string;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  return (
    <div className="panel-confirm">
      <p>{message}</p>
      <div className="panel-confirm-actions">
        <button onClick={onConfirm}>{confirm}</button>
        <button className="is-quiet" onClick={onCancel}>
          취소
        </button>
      </div>
    </div>
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
      <strong>기본 링크 · {previewProviderLabels[provider]}</strong>
      <small>공통 예습 대화 열기</small>
    </a>
  );
}

/** 러너가 이 시간 안에 안 보이면 안 붙은 것으로 친다(`AdminPage`와 같은 값). */
const RUNNER_STALE_MS = 120_000;

/**
 * 열려 있는 일감 한 줄을 사람 말로. **「만드는 중」은 러너가 집어 갔을 때만 쓴다.**
 *
 * 이 자리가 한동안 상태를 안 가리고 「만드는 중」을 먼저 적은 뒤 사정을 뒤에
 * 붙였다. 그래서 아무도 안 만들고 있을 때 이렇게 나왔다 —
 *
 *     Pre-Quiz 덱 — 만드는 중 · 러너를 기다리는 중 · 러너가 안 붙어 있습니다
 *
 * 세 토막이 서로 다른 말을 하고, 그중 첫 토막이 거짓이다. 읽는 사람은 기다리면
 * 되는 줄 알고 기다린다 — 노트북을 켜야 시작되는데. 서버가 일감과 러너 상태를
 * 같이 주는 까닭이 이걸 가르라는 것이므로(`GET …/prequiz-job`), 갈라서 **한 가지만**
 * 말한다.
 *
 * `stage`는 러너가 올린 것이라 `running`일 때만 쓸모가 있다. 대기 중인 일감의
 * `stage`는 서버가 줄을 세우며 넣어 둔 말이라, 여기서 다시 적으면 겹친다.
 */
function jobLine(job: PrequizJob, runner: RunnerBeat | null): string {
  const alive = runner?.lastSeen
    ? Date.now() - new Date(runner.lastSeen).getTime() < RUNNER_STALE_MS
    : false;
  if (!alive) {
    // 러너가 없으면 이 일감은 안 움직인다. 만들다 만 것과 아직 시작도 못 한 것을
    // 가른다 — 앞의 것은 다시 붙으면 이어 잡고(`claim`이 running부터 준다),
    // 뒤의 것은 띄우기만 하면 된다.
    return job.state === "running"
      ? `러너가 안 붙어 있습니다 · ${job.stage || "시작"}에서 멈췄습니다`
      : "러너가 안 붙어 있습니다 · 노트북에서 띄우면 집어 갑니다";
  }
  if (job.state === "running") return `${job.force ? "다시 " : ""}만드는 중 · ${job.stage || "시작"}`;
  // 줄은 섰고 러너도 있다. 그런데 한 번에 한 편만 만든다 — 앞 편이 있으면 그것부터다.
  const soon = runner?.busy ? "차례를 기다립니다 · 러너가 앞 편을 만드는 중입니다" : "러너가 곧 집어 갑니다";
  return job.force ? `다시 만듭니다 · ${soon}` : soon;
}

/**
 * 덱 한 줄. 학생에게는 받는 줄이고, **관리자에게는 만드는 자리다.**
 *
 * 덱이 없다는 것을 알아차리는 곳이 여기다 — 캘린더에서 강의를 눌러 「아직
 * 없습니다」를 본 순간. 그때 `/admin` 표까지 걸어가게 하면 대개 안 간다.
 *
 * 만드는 것은 노트북이므로 여기서 하는 일은 일감 한 줄을 적는 것까지다. 한 편에
 * 15분이 걸려서 누른 자리에서 기다릴 수 없고, 그래서 **진행이 이 줄로 돌아온다.**
 *
 * **두 갈래가 같은 부품을 쓴다**(`kind`). 예습과 복습은 재료도 만드는 명령도
 * 다르지만(그 갈래는 러너가 안다), 여기서 사람이 하는 일은 한 가지다 — 없는 것을
 * 보고 누르고, 진행을 같은 자리에서 읽는다. 갈라 두면 한쪽에 붙인 손질이 다른
 * 쪽에 안 붙는다.
 */
function DeckSlot({
  kind,
  label,
  file,
  lecture,
  onDownload,
  quiet,
}: {
  kind: DeckKind;
  label: string;
  file: LectureFile | undefined;
  lecture: LectureRef;
  onDownload: (file: LectureFile) => void;
  quiet?: boolean;
}) {
  const isAdmin = Boolean(useMe()?.isAdmin);
  if (!isAdmin) {
    return <DeckAction file={file} label={label} onDownload={onDownload} quiet={quiet} />;
  }
  return (
    <DeckMake kind={kind} label={label} file={file} lecture={lecture} onDownload={onDownload} quiet={quiet} />
  );
}

/** 「다시 만들기」를 누르면 무엇이 일어나는지. **갈래마다 재료가 다르다.** */
const REMAKE_MESSAGE: Record<DeckKind, string> = {
  pre: "지금 있는 문항을 버리고, 저장된 예습 링크로 처음부터 다시 만듭니다. 15분쯤 걸리고 다 되면 이 자리의 덱이 새것으로 바뀝니다. 이미 받아 간 사람의 덱은 그대로 남습니다.",
  main: "지금 있는 문항을 버리고, 올해 강의록으로 처음부터 다시 만듭니다. 15분쯤 걸리고 다 되면 이 자리의 덱이 새것으로 바뀝니다. 이미 받아 간 사람의 덱은 그대로 남습니다.",
};

/**
 * 관리자가 보는 덱 줄. 없으면 만들고, 있으면 **다시 만들 수 있다.**
 *
 * 둘을 한 부품으로 두는 이유는 일감이 하나이기 때문이다. 만드는 중이라는 말도,
 * 실패했다는 말도, 덱이 있든 없든 같은 자리에서 같은 모양으로 돌아와야 한다.
 *
 * **일감을 갈래로 물어본다**(`?kind=`). 안 가르면 복습을 만드는 중이라는 말이
 * 예습 자리에도 떠서, 사람이 누르지 않은 것을 기다리게 된다.
 */
function DeckMake({
  kind,
  label,
  file,
  lecture,
  onDownload,
  quiet,
}: {
  kind: DeckKind;
  label: string;
  file: LectureFile | undefined;
  lecture: LectureRef;
  onDownload: (file: LectureFile) => void;
  quiet?: boolean;
}) {
  const base = `/api/admin/lectures/${encodeURIComponent(lecture.subject)}/${encodeURIComponent(lecture.runId)}`;
  const [job, setJob] = useState<PrequizJob | null>(null);
  const [runner, setRunner] = useState<RunnerBeat | null>(null);
  const [asking, setAsking] = useState(false);
  const [askingRemake, setAskingRemake] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(() => {
    api<{ job: PrequizJob | null; runner: RunnerBeat | null }>(`${base}/prequiz-job?kind=${kind}`)
      .then((answer) => {
        setJob(answer.job);
        setRunner(answer.runner);
      })
      .catch(() => {});
  }, [base, kind]);

  useEffect(load, [load]);

  const open = job?.state === "queued" || job?.state === "running";
  useEffect(() => {
    // 도는 동안만 다시 읽는다. 한 편에 15분이라 사람이 패널을 닫았다 열어야
    // 진행이 보이면, 그 진행은 없는 것과 같다.
    if (!open) return;
    const timer = window.setInterval(load, 10_000);
    return () => window.clearInterval(timer);
  }, [open, load]);

  // 끝나면 강의 상세를 다시 읽는다. **덱이 바뀌었는데 이 줄은 옛 크기를 들고
  // 있다** — 다 됐다는 말과 눈앞의 것이 어긋나면 사람은 새로고침을 배워야 한다.
  // 예습 링크가 밖에서 저장될 때 쓰는 신호를 그대로 쓴다(상세를 다시 읽는 일이다).
  const wasOpen = useRef(false);
  useEffect(() => {
    if (wasOpen.current && !open && job?.state === "done") bumpPreviewVersion();
    wasOpen.current = open;
  }, [open, job?.state]);

  async function ask(force: boolean) {
    setAsking(true);
    setError("");
    try {
      const answer = await api<{ job: PrequizJob }>(`${base}/prequiz-job?kind=${kind}`, {
        method: "POST",
        body: force ? JSON.stringify({ force: true }) : undefined,
      });
      setJob(answer.job);
      // 이미 러너가 집어 간 편에는 「다시」가 안 걸린다. 조용히 넘기면 15분을
      // 기다린 끝에 옛 덱이 그대로 있는 것을 보게 된다.
      if (force && !answer.job.force) {
        setError("이미 만드는 중이라 이번 판에는 안 걸립니다. 끝난 뒤에 다시 눌러 주세요.");
      }
    } catch (cause) {
      setError((cause as Error).message);
    } finally {
      setAsking(false);
    }
  }

  const key = quiet ? "" : " is-key";
  // 실패는 남긴다. 조용히 지우면 「눌렀는데 아무 일도 없었다」가 된다.
  const failure = (
    <>
      {job?.state === "failed" ? <p className="notice is-error">{job.message}</p> : null}
      {error ? <p className="notice is-error">{error}</p> : null}
    </>
  );

  if (file) {
    return (
      <>
        <div className="panel-row">
          <DeckAction file={file} label={label} onDownload={onDownload} quiet={quiet} />
          {/* 덱이 이상하다는 것을 아는 사람은 그것을 받아 본 사람이다. 그 사람이
              서 있는 자리가 이 줄이라 여기에 붙인다. 링크 다시 만들기와 같은
              크기·같은 모양이다 — 드물게 하는 일이라는 뜻이 크기에 들어 있다. */}
          <Remake
            label={`${label} 다시 만들기`}
            busy={job?.state === "running"}
            busyLabel="다시 만드는 중…"
            disabled={open || asking}
            onClick={() => setAskingRemake(true)}
          />
        </div>
        {askingRemake ? (
          <RemakeConfirm
            message={REMAKE_MESSAGE[kind]}
            confirm="다시 만들기"
            onConfirm={() => {
              setAskingRemake(false);
              void ask(true);
            }}
            onCancel={() => setAskingRemake(false)}
          />
        ) : null}
        {/* 덱이 있으므로 이 줄은 자리를 뺏지 않고 아래에 붙는다. */}
        {open && job ? <p className="panel-hint">{label} — {jobLine(job, runner)}</p> : null}
        {failure}
      </>
    );
  }

  if (open && job) {
    // `is-empty`는 한 줄짜리 자리다(`display: block`). 옆의 「아직 없습니다」와
    // 같은 꼴로 적는다 — strong·small을 넣으면 저 혼자 두 줄로 서서 눈에 걸린다.
    return <span className={`panel-action${key} is-empty`}>{label} — {jobLine(job, runner)}</span>;
  }

  return (
    <>
      <button className={`panel-action${key}`} disabled={asking} onClick={() => void ask(false)}>
        <strong>{label} 만들기</strong>
        <small>{asking ? "맡기는 중…" : "아직 없습니다 · 눌러서 만듭니다"}</small>
      </button>
      {failure}
    </>
  );
}

function DeckAction({
  file,
  label,
  onDownload,
  quiet = false,
}: {
  file: LectureFile | undefined;
  label: string;
  onDownload: (file: LectureFile) => void;
  /** 위에 그 덱의 웹 풀이가 서 있는가. 그러면 이 줄은 한 단 낮게 눕는다. */
  quiet?: boolean;
}) {
  const key = quiet ? "" : " is-key";
  // 아직 없는 것도 자리를 남긴다. 목록에서 빠지면 "없다"와 "이 강의에는 원래
  // 해당 없다"를 구분할 수 없다.
  if (!file) return <span className={`panel-action${key} is-empty`}>{label} — 아직 없습니다</span>;
  return (
    <button className={`panel-action${key} is-download`} onClick={() => onDownload(file)}>
      <strong>{label}</strong>
      <small>{fileSize(file.sizeBytes)} · 내려받기</small>
    </button>
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

/** 1MB 아래를 `0.0MB`로 적으면 크기를 말한 것이 아니라 안 말한 것이 된다. */
function fileSize(bytes: number) {
  return bytes < 1024 * 1024 ? `${Math.max(1, Math.round(bytes / 1024))}KB` : `${(bytes / 1024 / 1024).toFixed(1)}MB`;
}
