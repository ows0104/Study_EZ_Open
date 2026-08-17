import { useEffect, useRef, useState } from "react";
import { api, downloadSignedFile } from "../api";
import type { LectureDetail, LectureFile, LectureRef } from "../types";
import {
  absoluteUrl,
  extensionInstalled,
  requestPreview,
  usePreviewVersion,
  watchSharedLink,
} from "../bridge/previewBridge";
import { EXTENSION_DOWNLOAD_URL } from "../bridge/protocol";
import { PROMPT_TOKENS, renderPreviewPrompt, SHARED_PREVIEW_PROMPT } from "../lecture/previewPrompt";
import { usePreviewPrompt } from "../lecture/usePreviewPrompt";
import { useMe } from "../useMe";
import { categoryLabel, type CalendarEntry } from "./entries";
import { lectureHref } from "./EventChip";

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
          {detail ? <NotesFact detail={detail} /> : null}
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

/**
 * 필기는 누를 것이 아니라 무엇이 붙어 있는지만 알면 되는 정보다. 다만 파일
 * 이름까지는 보여 준다 — 예습할 때 ChatGPT에 붙일 파일이 이것이라서, 이름을
 * 모르면 내려받은 것 중 어느 것인지 못 고른다.
 */
function NotesFact({ detail }: { detail: LectureDetail }) {
  const rows: [string, LectureFile | undefined][] = [
    ["작년", detail.files.find((file) => file.kind === "notes_prev")],
    ["올해", detail.files.find((file) => file.kind === "notes_current")],
  ];
  const author = detail.author ? `${detail.author}${detail.version ? `v${detail.version}` : ""}` : "";
  return (
    <div className="event-panel-fact">
      <dt>필기</dt>
      <dd>
        <ul className="event-panel-notes">
          {rows.map(([label, file]) => (
            <li key={label} className={file ? "" : "is-empty"}>
              <span>{label}</span>
              {file ? (
                <>
                  <b>{file.filename}</b>
                  <small>{fileSize(file.sizeBytes)}</small>
                </>
              ) : (
                <b>아직 없음</b>
              )}
            </li>
          ))}
        </ul>
        {author ? <small className="event-panel-author">필기 {author}</small> : null}
      </dd>
    </div>
  );
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
 * 강조하는 셋. 예습 링크 · Pre-Quiz 덱 · Main-Quiz 덱.
 *
 * 링크는 누르면 바로 열리고 덱은 누르면 바로 받는다. 중간에 확인할 화면을
 * 두지 않는다 — 그 셋이 이 패널의 존재 이유다.
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

  return (
    <div className="event-panel-actions">
      <PreviewAction lecture={lecture} detail={detail} base={base} onError={setError} />

      <DeckAction file={fileOf("pre_apkg")} label="Pre-Quiz 덱" count={quiz?.itemCount} onDownload={download} />
      {/* 웹 풀이는 좁은 패널에 담기지 않는다. 문항과 해설이 있어야 할 자리라
          강의 화면으로 보낸다. 덱이 기본이므로 눈에 덜 걸리게 둔다. */}
      {quiz ? (
        <a className="panel-subaction" href={lectureHref(lecture)} target="_blank" rel="noreferrer">
          웹에서 풀기
          {quiz.answered ? ` · ${quiz.answered}/${quiz.itemCount}개 풀었습니다` : ""}
        </a>
      ) : null}

      <DeckAction file={fileOf("main_apkg")} label="Main-Quiz 덱" onDownload={download} />

      {error ? <p className="notice is-error">{error}</p> : null}
    </div>
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
 * 없으므로 한 번에 셋을 한다 — 필기를 내려받고, 프롬프트를 복사하고, ChatGPT를
 * 연다. 사용자는 붙이고 붙여넣기만 하면 된다.
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
  const promptStore = usePreviewPrompt();
  const isAdmin = Boolean(useMe()?.isAdmin);
  const lectureId = `${lecture.subject}/${lecture.runId}`;
  const notesPrev = detail.files.find((file) => file.kind === "notes_prev");
  const editor = (
    <PromptEditor store={promptStore} detail={detail} open={showPrompt} onToggle={() => setShowPrompt((o) => !o)} />
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
    return (
      <>
        {detail.preview?.shareUrl ? <SharedOpen url={detail.preview.shareUrl} lectureId={lectureId} /> : null}
        <a className="panel-action is-key is-download" href={EXTENSION_DOWNLOAD_URL} download>
          <strong>예습 브리지 내려받기</strong>
          <small>설치하면 필기와 프롬프트가 ChatGPT에 자동으로 들어갑니다</small>
        </a>
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
      </>
    );
  }

  // 작년 필기가 없으면 새로 만들 수는 없다. 다만 이미 만들어진 링크는 그대로
  // 열려야 하므로 여기서 통째로 돌려보내지 않는다.
  const canMake = Boolean(notesPrev);

  return (
    <>
      {/* 기본 링크 — 강의당 하나, 반 전체가 같은 것을 읽는다. 문구가 고정이라
          누가 만들었든 같은 것을 물은 대화다. 만드는 것은 관리자뿐이다. */}
      {detail.preview?.shareUrl ? (
        <>
          <div className="panel-row">
            <SharedOpen url={detail.preview.shareUrl} lectureId={lectureId} />
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
          <small>고정 프롬프트로 묻고, 만들어진 공유 링크를 모두에게 냅니다</small>
        </button>
      ) : (
        <span className="panel-action is-key is-empty">기본 링크 — 아직 없습니다</span>
      )}

      {/* 개인 링크 — 사람마다 하나. 프롬프트도 자기 것으로 묻는다. */}
      {detail.myPreview?.conversationUrl ? (
        <div className="panel-row">
          {/* 저장되면 이 자리가 회색 버튼("개인 예습 시작")에서 이 파란 줄로
              바뀐다. 색이 곧 "내 대화가 저장돼 있다"는 표시다.

              주소는 title에 그대로 둔다 — 빈 ChatGPT가 뜰 때 무엇이 저장돼
              있는지 볼 데가 여기밖에 없다. */}
          <a
            className="panel-action is-key"
            href={detail.myPreview.conversationUrl}
            title={detail.myPreview.conversationUrl}
            target="_blank"
            rel="noreferrer"
          >
            <strong>개인 링크</strong>
            <small>내 예습 대화 이어서 열기</small>
          </a>
          {canMake ? (
            // 자기 것이라 묻지 않는다. 옛 대화는 ChatGPT에 그대로 남아 있고
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
        <button className="panel-action" onClick={() => start("personal")} disabled={Boolean(busy)}>
          <strong>{busy === "personal" ? "여는 중…" : "개인 예습 시작"}</strong>
          <small>내 프롬프트로 새 대화를 엽니다</small>
        </button>
      ) : null}
      {editor}
    </>
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
  disabled,
  onClick,
}: {
  label: string;
  busy: boolean;
  disabled: boolean;
  onClick: () => void;
}) {
  return (
    <button
      className={busy ? "panel-remake is-busy" : "panel-remake"}
      onClick={onClick}
      disabled={disabled}
      aria-label={busy ? "여는 중…" : label}
      aria-busy={busy}
      title={label}
    >
      <span aria-hidden="true">⟳</span>
    </button>
  );
}

/**
 * 기본 링크를 다시 만들기 전에 한 번 묻는다.
 *
 * 개인 링크와 달리 이것은 반 전체가 보는 값이고, 이미 그 링크로 Pre-Quiz가
 * 만들어졌을 수도 있다. 되돌리려면 다시 만드는 수밖에 없다.
 *
 * `window.confirm` 대신 자리에서 묻는다 — 새 탭을 여는 흐름이라 모달이 팝업
 * 차단과 얽히고, 무엇을 바꾸는지 문장으로 적을 자리도 없다.
 */
function RemakeConfirm({ onConfirm, onCancel }: { onConfirm: () => void; onCancel: () => void }) {
  return (
    <div className="panel-confirm">
      <p>모두가 보는 링크가 새 대화로 바뀝니다. 옛 링크는 ChatGPT에 그대로 남지만 여기서는 안 보입니다.</p>
      <div className="panel-confirm-actions">
        <button onClick={onConfirm}>바꾸기</button>
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
function SharedOpen({ url, lectureId }: { url: string; lectureId: string }) {
  return (
    <a
      className="panel-action is-key"
      href={url}
      target="_blank"
      rel="noreferrer"
      onClick={() => watchSharedLink(lectureId, url)}
    >
      <strong>기본 링크</strong>
      <small>공통 예습 대화 열기</small>
    </a>
  );
}

function DeckAction({
  file,
  label,
  count,
  onDownload,
}: {
  file: LectureFile | undefined;
  label: string;
  count?: number;
  onDownload: (file: LectureFile) => void;
}) {
  // 아직 없는 것도 자리를 남긴다. 목록에서 빠지면 "없다"와 "이 강의에는 원래
  // 해당 없다"를 구분할 수 없다.
  if (!file) return <span className="panel-action is-key is-empty">{label} — 아직 없습니다</span>;
  return (
    <button className="panel-action is-key is-download" onClick={() => onDownload(file)}>
      <strong>{label}</strong>
      <small>
        {fileSize(file.sizeBytes)}
        {count ? ` · ${count}문항` : ""} · 내려받기
      </small>
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
  open,
  onToggle,
}: {
  store: ReturnType<typeof usePreviewPrompt>;
  detail: LectureDetail;
  open: boolean;
  onToggle: () => void;
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
    <>
      <button className="panel-subaction is-toggle" onClick={onToggle}>
        프롬프트 {open ? "접기" : "고치기"}
        {store.isCustom ? <em className="panel-badge">내 것</em> : null}
      </button>
      {open ? (
        <div className="prompt-editor">
          {/* 기본 링크의 문구는 고칠 수 없다. 반이 하나의 대화를 읽으니 무엇을
              물었는지도 하나여야 한다. 다만 보이지도 않으면 확인할 길이 없다. */}
          <div className="prompt-fixed">
            <h4>기본 링크 — 고정</h4>
            <pre>{SHARED_PREVIEW_PROMPT}</pre>
          </div>
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
      ) : null}
    </>
  );
}

/** 1MB 아래를 `0.0MB`로 적으면 크기를 말한 것이 아니라 안 말한 것이 된다. */
function fileSize(bytes: number) {
  return bytes < 1024 * 1024 ? `${Math.max(1, Math.round(bytes / 1024))}KB` : `${(bytes / 1024 / 1024).toFixed(1)}MB`;
}
