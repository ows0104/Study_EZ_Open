import { useEffect, useRef, useState } from "react";
import { BankPanel } from "../bank/BankPanel";
import { useMainQuizEntry } from "../bank/useMainQuizEntry";
import { api, downloadSignedFile, openSignedFile } from "../api";
import { BundleButton } from "../bundle/BundleButton";
import { decksIn, useBundleDecks } from "../bundle/decks";
import { usePreviewVersion } from "../bridge/previewBridge";
import { Link } from "react-router-dom";
import { useMe } from "../useMe";
import { bankHref, lectureHref, legacyMainHref, quizHref } from "../links";
import { FeedbackButton } from "../feedback/FeedbackButton";
import { type LectureDetail, type LectureFile, type LectureRef } from "../types/lectures";
import type { CardProgress } from "../types/mastery";
import { categoryLabel, type CalendarEntry } from "./entries";
import { fullCode, splitSubject, type DisplayInfo } from "./kinds";
import { ReviewMeter } from "./ChipLearning";
import { rootRate } from "../bank/useRootCatalog";
import { DeckSlot } from "./DeckSlot";
import { cardsHash } from "../lecture/LectureCards";
import { ActionCard, fileSize, PanelGroup } from "./panelShared";
import { PreviewAction } from "./PreviewAction";
import { ReviewAction } from "./ReviewAction";
import { JokboAction } from "./JokboAction";
import { LectureMemo, ReadEditor } from "./ReadEditor";
import { PreviewSourceNotice, ProfessorInfo, ProfTag, previewNotesLabel } from "./ProfessorInfo";
import { useOptionalVersion } from "../bank/optionalExclusion";

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
export function EventPanel({
  entry,
  info,
  onClose,
  initialLecture = 0,
}: {
  entry: CalendarEntry;
  info?: DisplayInfo;
  onClose: () => void;
  /** 처음 고를 강의(한 칸에 강의가 여럿일 때). 강의 목록이 누른 행의 강의로 연다. */
  initialLecture?: number;
}) {
  const panel = useRef<HTMLElement>(null);
  const [chosen, setChosen] = useState(initialLecture);
  const lecture: LectureRef | undefined = entry.lectures[chosen];
  const { detail, error } = useLectureDetail(lecture);

  useEffect(() => {
    // 패널을 연 것이 키보드일 수 있다. 초점을 안 옮기면 다음 Tab이 패널이 아니라
    // 남은 칸들로 흘러간다. 닫을 때는 누른 칸으로 돌려준다.
    const restore = document.activeElement as HTMLElement | null;
    panel.current?.focus({ preventScroll: true });
    function onKey(event: KeyboardEvent) {
      if (document.querySelector("dialog[open]")) return;
      if (event.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("keydown", onKey);
      restore?.focus?.({ preventScroll: true });
    };
  }, [onClose]);

  const primary = splitSubject(entry.detail).title || entry.title;
  const isAdmin = Boolean(useMe()?.isAdmin);
  const source = detail ? detail.previewSource : lecture?.previewSource;
  const group = info?.kind === "tbl" || info?.kind === "cbl";

  return (
    <>
      {/* 좁은 화면에서만 보인다. 넓은 화면에서는 패널이 캘린더를 덮지 않으므로
          가릴 것도, 눌러서 닫을 것도 없다. */}
      <div className="panel-scrim" onClick={onClose} aria-hidden="true" />
      <aside className="event-panel" aria-label={primary} tabIndex={-1} ref={panel}>
        <header className="event-panel-head">
          <span className="event-panel-tags">
            <span className={`event-panel-kind is-${entry.category}`}>{fullCode(info) || categoryLabel(entry.category)}</span>
            {info?.block ? <span className="event-panel-block">{info.block}</span> : null}
          </span>
          <button className="is-quiet event-panel-close" onClick={onClose} aria-label="닫기">
            ✕
          </button>
        </header>

        <h2 className="event-panel-title">{primary}</h2>
        {entry.professor ? (
          <p className="event-panel-prof">
            <span>{group ? "분반" : "교수"}</span>
            {entry.professor}
            <ProfTag values={[source]} />
          </p>
        ) : null}
        <PreviewSourceNotice value={source} />

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
            <KeyActions
              lecture={lecture}
              detail={detail}
              jokbo={<JokboAction eventId={entry.id} />}
            />
          ) : error ? null : (
            <p className="event-panel-loading">자료를 불러오는 중…</p>
          )
        ) : (
          /* 없다는 것을 말하는 자리다. 이것이 없으면 "아직 안 올라옴"과
             "눌러도 안 되는 화면"을 구분할 수 없다. */
          <>
            <p className="event-panel-empty">
              아직 올라온 자료가 없습니다.
              <small>예습·퀴즈가 준비되면 이 칸에 점이 붙습니다.</small>
            </p>
            {/* 족보는 필기(강의 자료)보다 먼저 있다 — 자료가 없는 칸에도 선다. */}
            <div className="event-panel-actions"><JokboAction eventId={entry.id} /></div>
          </>
        )}

        {/* 관리자만: 예전 패널의 관리 도구·필기·강의 정보. 학생 화면에는 두지 않는다(2026-11 개편). */}
        {isAdmin && lecture && detail ? (
          <details className="event-panel-admin">
            <summary>관리자</summary>
            <AdminTools lecture={lecture} detail={detail} />
            <ProfessorInfo value={source} />
            <dl className="event-panel-facts">
              <Fact label="일시"><time>{entry.date} · {entry.startTime}–{entry.endTime}</time></Fact>
              {entry.course ? <Fact label="과목">{entry.course}</Fact> : null}
              <Fact label="교시명">{entry.title}</Fact>
              {detail.author ? <Fact label="필기자">{detail.author}{detail.version ? ` v${detail.version}` : ""}</Fact> : null}
            </dl>
            <Link className="event-panel-more" to={lectureHref(lecture)}>강의 화면 전체 보기 →</Link>
          </details>
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
    const path = `/api/lectures/${encodeURIComponent(lecture.subject)}/${encodeURIComponent(lecture.runId)}`;
    let request = 0;
    function refresh() {
      const current = ++request;
      api<LectureDetail>(path)
        .then(next => { if (live && current === request) { setDetail(next); setError(""); } })
        .catch((cause: Error) => { if (live && current === request) setError(cause.message); });
    }
    refresh();
    window.addEventListener("focus", refresh);
    return () => {
      live = false;
      window.removeEventListener("focus", refresh);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, version]);

  // 강의가 바뀌면 앞 강의의 값을 잠깐이라도 보여 주지 않는다.
  useEffect(() => {
    setDetail(null);
  }, [key]);

  return { detail, error };
}

type Study = { mastery?: LectureDetail["mastery"]; cardProgress?: CardProgress | null };

/** 패널의 카드 단계·오늘 복습 수. 강의 목록과 같은 `/api/timetable/study-progress`를 이 강의 하나로 부른다. */
function useLectureStudy(lecture: LectureRef): Study | null {
  const [study, setStudy] = useState<Study | null>(lecture.cardProgress ? { mastery: lecture.mastery, cardProgress: lecture.cardProgress } : null);
  const optional = useOptionalVersion();
  useEffect(() => {
    const controller = new AbortController();
    api<{ lectures: (Study & { subject: string; runId: string })[] }>("/api/timetable/study-progress", {
      method: "POST", signal: controller.signal,
      body: JSON.stringify({ lectures: [{ subject: lecture.subject, runId: lecture.runId }] }),
    }).then(data => {
      if (!controller.signal.aborted && data.lectures[0]) setStudy(data.lectures[0]);
    }).catch(() => {});
    return () => controller.abort();
  }, [lecture.subject, lecture.runId, optional]);
  return study;
}

/**
 * 「카드 고치기」 — 강의 화면의 「카드 검토」 절로 곧장 간다. **관리자에게만 선다**
 * (`cardReview` 가 관리자 응답에만 있다).
 *
 * 2026-09-23 관리자 지시 — 「사이드 패널에서도 고치기로 넘어갈 수 있게 해줘.」
 * 고치는 화면을 패널 안에 들이지 않은 이유는 폭이다 — 질문·답·해설 세 칸을 여러
 * 줄로 고치는 일이라 패널 폭에서는 한 카드도 한눈에 안 들어온다. 강의 화면 전체
 * 보기와 같은 길(새 탭)로 가서 캘린더는 그대로 남는다.
 *
 * **검토 표시된 카드가 있는 갈래에만 선다**(같은 날 관리자 — 「카드 검토할때
 * 검토표시된것만 확인하고 고치려고 하는 거였어」). 안 본 것이 있으면 경고색이다.
 */
function CardFixLinks({
  lecture,
  counts,
}: {
  lecture: LectureRef;
  counts: LectureDetail["cardReview"];
}) {
  const kinds = (["pre", "main"] as const).filter((kind) => (counts?.[kind]?.flagged ?? 0) > 0);
  if (!counts || !kinds.length) return null;
  return (
    <div className="card-fix-links">
      {kinds.map((kind) => {
        const count = counts[kind]!;
        return (
          <a
            key={kind}
            className={`card-fix-link${count.open ? " is-flagged" : ""}`}
            href={lectureHref(lecture) + cardsHash(kind)}
            target="_blank"
            rel="noreferrer"
          >
            {kind === "pre" ? "예습" : "복습"} 카드 고치기
            <small>
              검토 표시 {count.flagged}장{count.open ? ` · 안 봄 ${count.open}장` : " · 다 봤음"}
            </small>
          </a>
        );
      })}
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
 * 강조하는 셋. 예습 · Pre-Quiz · Main-Quiz.
 *
 * 링크는 누르면 바로 열리고 덱은 누르면 바로 받는다. 중간에 확인할 화면을
 * 두지 않는다 — 그 셋이 이 패널의 존재 이유다.
 *
 * **셋을 갈래로 묶고 색을 나눴다(2026-08-31 관리자 지시).** 전에는 버튼 예닐곱이
 * 같은 파랑으로 이어져 서 있어서 어디까지가 예습이고 어디부터가 Pre-Quiz인지
 * 글자를 읽어야 알았다. 머리에 이름·색·때(언제 하는 것인가)를 달아 둔다.
 *
 * **필기는 그 셋이 아니다.** 한동안 여기 큰 버튼으로 세워 뒀는데 주요 버튼만큼
 * 눈에 걸렸다. 아래 조용한 줄로 돌려보내되, 누르면 열리는 것은 그대로 둔다.
 */
const emptyCards: CardProgress = { total: 0, seen: 0, unseen: 0, recognized: 0, retrieving: 0, retained: 0,
  newRemaining: 0, reviewDue: 0, suspended: 0 };

function KeyActions({
  lecture,
  detail,
  jokbo,
}: {
  lecture: LectureRef;
  detail: LectureDetail;
  /** 복습 아래 「족보」 칸(2026-11-13). 시간표 칸에 붙으므로 바깥에서 만든다. */
  jokbo?: React.ReactNode;
}) {
  const base = `/api/lectures/${encodeURIComponent(lecture.subject)}/${encodeURIComponent(lecture.runId)}`;
  const [error, setError] = useState("");
  const fileOf = (kind: LectureFile["kind"]) => detail.files.find((file) => file.kind === kind);
  const study = useLectureStudy(lecture);
  const { entry: mainQuizEntry } = useMainQuizEntry(lecture.subject, lecture.runId);
  // 학습률은 Main-Quiz 하나(2026-11-11): 서버가 계산한 값. 강의 목록·캘린더 칸·시험 계획과 같다.
  const mastery = detail.mastery ?? study?.mastery ?? null;
  const overview = mainQuizEntry?.mode === "structured" ? mainQuizEntry.overview : null;
  const opened = Boolean(lecture.marks?.mainQuiz || overview);
  const rate = opened ? Math.max(0, Math.min(100, rootRate(overview?.summary) ?? mastery?.score ?? 0)) : null;
  const questions = overview?.questionProgress;
  const cards: CardProgress | null = questions ? { ...emptyCards, ...questions, seen: questions.total - questions.unseen } : null;

  async function download(file: LectureFile) {
    try {
      await downloadSignedFile(`${base}/files/${file.id}?purpose=download`, file.filename);
    } catch (cause) {
      setError((cause as Error).message);
    }
  }

  const preDone = Boolean(detail.prequiz && detail.prequiz.itemCount > 0 && detail.prequiz.answered >= detail.prequiz.itemCount);
  const preDeck = fileOf("pre_apkg");
  const mainDeck = fileOf("main_apkg");
  const prevNotes = fileOf("notes_prev");
  const currentNotes = fileOf("notes_current");

  return (
    <div className="event-panel-actions">
      <PreviewAction
        lecture={lecture}
        detail={detail}
        base={base}
        onError={setError}
        trailing={detail.prequiz ? (
          <Link className="action-button is-quiz is-pre" to={quizHref("pre", lecture)}>▶ 예습 퀴즈</Link>
        ) : (
          <span className="action-button is-quiz is-pre is-disabled" aria-disabled="true">▶ 예습 퀴즈</span>
        )}
      />
      <ReviewAction
        lecture={lecture}
        detail={detail}
        base={base}
        onError={setError}
        open
        trailing={opened ? (
          <Link className="action-button is-quiz is-review" to={bankHref(lecture)}>
            ▶ 복습 퀴즈{questions?.reviewDue ? <b>{questions.reviewDue}</b> : null}
          </Link>
        ) : (
          <span className="action-button is-quiz is-review is-disabled" aria-disabled="true">▶ 복습 퀴즈</span>
        )}
      />

      {jokbo}

      <section className="panel-stats" aria-label="통계">
        <h3>통계</h3>
        <div className="stat-row">
          <span className="stat-label">회독</span>
          <ReadEditor lecture={lecture} base={base} preOpen={Boolean(detail.prequiz)} preDone={preDone}
            initial={detail.noteReads ?? 0} onError={setError} />
        </div>
        <div className="stat-row">
          <span className="stat-label">학습률</span>
          <span className="stat-rate">
            <b className={`rate-text ${rateBand(rate)}`}>{rate === null ? "0%" : `${rate}%`}</b>
            <ReviewMeter score={rate} />
          </span>
        </div>
        <div className="stat-row is-top">
          <span className="stat-label">메모</span>
          <LectureMemo base={base} initial={detail.myMemo ?? ""} onError={setError} />
        </div>
        {cards ? (
          <div className="stat-row is-top">
            <span className="stat-label">문항</span>
            <StageSummary cards={cards} />
          </div>
        ) : null}
      </section>

      {/* 예습·복습에 쓰는 강의록(2026-11-10 사용자 지시). 덱과 상관없이, 파일이 있으면 보인다. */}
      {prevNotes || currentNotes ? (
        <section className="panel-stats panel-info" aria-label="정보">
          <h3>정보</h3>
          {prevNotes ? (
            <div className="stat-row">
              <span className="stat-label">예습</span>
              <NotesName filename={prevNotes.filename} />
            </div>
          ) : null}
          {currentNotes ? (
            <div className="stat-row">
              <span className="stat-label">복습</span>
              <NotesName filename={currentNotes.filename} />
            </div>
          ) : null}
        </section>
      ) : null}

      <div className="event-panel-foot">
        {preDeck || mainDeck ? (
          <span className="deck-links">
            덱 다운로드
            {preDeck ? <button type="button" onClick={() => void download(preDeck)}>예습</button> : null}
            {mainDeck ? <button type="button" onClick={() => void download(mainDeck)}>복습</button> : null}
          </span>
        ) : <span />}
        <FeedbackButton launch={{ className: "ghost-button", content: "오류 제보" }} />
      </div>

      {error ? <p className="notice is-error">{error}</p> : null}
    </div>
  );
}

/**
 * 강의록 파일명. 길면 강의명 쪽만 줄이고 끝의 판(v3)은 늘 보인다(2026-11-10 사용자 지시).
 * 필기 파일명 꼴은 `[260813_03]제목(교수)_필기자v3.pdf`(runner/filenames.py). 앞의 날짜·교시는 떼고 전체 이름은 title에 둔다.
 */
export function splitNotesName(filename: string): { head: string; version: string } {
  const bare = filename.normalize("NFC").replace(/\.[a-z0-9]{1,5}$/i, "")
    .replace(/^\s*[[(]\s*\d{6}\s*_\s*\d{1,2}(?:\s*~\s*\d{1,2})?\s*[\])}]\s*/, "");
  const tail = bare.match(/[vV]\s*\.?\s*(\d+)\s*$/);
  if (!tail) return { head: bare.trim(), version: "" };
  return { head: bare.slice(0, tail.index).replace(/[\s_]+$/, ""), version: `v${tail[1]}` };
}

function NotesName({ filename }: { filename: string }) {
  const { head, version } = splitNotesName(filename);
  return (
    <span className="notes-name" title={filename}>
      <span className="notes-name-head">{head}</span>
      {version ? <span className="notes-name-version">{version}</span> : null}
    </span>
  );
}

/** 학습률 25% 구간 색(2026-11 개편). 낮을수록 위기 색, 높을수록 안심 색 — 카드 단계 색과 같은 줄기. */
function rateBand(rate: number | null) {
  if (rate === null) return "is-closed";
  if (rate < 25) return "is-band1";
  if (rate < 50) return "is-band2";
  if (rate < 75) return "is-band3";
  return "is-band4";
}

/** 미열람 · 인지 · 인출 · 저장(운영 Quiz Bank 네 단계, 「기억 유지」는 「저장」으로 부른다). */
const STAGES = [
  ["unseen", "미열람"], ["recognized", "인지"], ["retrieving", "인출"], ["retained", "저장"],
] as const;

function StageSummary({ cards }: { cards: CardProgress }) {
  return (
    <span className="stage-summary">
      <span className="stage-legend">
        {STAGES.map(([key, label]) => (
          <span key={key}><i className={`stage-dot stage-${key}`} />{label}<b className={`stage-text-${key}`}>{cards[key]}</b></span>
        ))}
      </span>
      <span className="stage-bar" role="img" aria-label={STAGES.map(([key, label]) => `${label} ${cards[key]}장`).join(" · ")}>
        {STAGES.map(([key]) => (cards[key] > 0 ? <span key={key} className={`stage-${key}`} style={{ flex: cards[key] }} /> : null))}
      </span>
    </span>
  );
}

/**
 * 관리자 도구. 예전 패널의 Pre-Quiz 덱 만들기·문제은행 관리·기존 Main-Quiz·카드 고치기·블럭 덱·필기를 그대로 둔다.
 * 학생 화면에서는 「관리자」 접힘째 빠진다(2026-11 개편).
 */
function AdminTools({ lecture, detail }: { lecture: LectureRef; detail: LectureDetail }) {
  const base = `/api/lectures/${encodeURIComponent(lecture.subject)}/${encodeURIComponent(lecture.runId)}`;
  const [showBundles, setShowBundles] = useState(false);
  const bundles = useBundleDecks(showBundles, new URLSearchParams({ subject: lecture.subject }).toString());
  const [error, setError] = useState("");
  const fileOf = (kind: LectureFile["kind"]) => detail.files.find((file) => file.kind === kind);

  async function download(file: LectureFile) {
    try {
      await downloadSignedFile(`${base}/files/${file.id}?purpose=download`, file.filename);
    } catch (cause) {
      setError((cause as Error).message);
    }
  }

  async function open(file: LectureFile) {
    try {
      await openSignedFile(`${base}/files/${file.id}?inline=1&purpose=view`);
    } catch (cause) {
      setError((cause as Error).message);
    }
  }

  function webSolve(progress: LectureDetail["prequiz"]) {
    if (!progress) return undefined;
    return (tools: React.ReactNode) => (
      <ActionCard
        shape="is-lead"
        hit={
          <Link className="panel-action-hit" to={quizHref("pre", lecture)}>
            <strong>웹에서 풀기</strong>
            <small>{progress.itemCount}장</small>
          </Link>
        }
        tools={tools}
      />
    );
  }

  return (
    <div className="event-panel-admin-body">
      <PanelGroup tone="pre" title="Pre-Quiz">
        <DeckSlot
          kind="pre"
          label="덱"
          file={fileOf("pre_apkg")}
          lecture={lecture}
          onDownload={download}
          before={webSolve(detail.prequiz)}
          blocked={
            detail.preview?.shareUrl
              ? undefined
              : { short: "예습 링크 대기", why: "예습 링크를 먼저 저장하세요. Pre-Quiz는 그 대화로 만듭니다." }
          }
        />
      </PanelGroup>
      <BankPanel lecture={lecture} detail={detail} />
      {detail.mainquiz || fileOf("main_apkg") ? (
        <details className="panel-hint legacy-main">
          <summary>기존 Main-Quiz 자료</summary>
          {detail.mainquiz ? <Link to={legacyMainHref(lecture)}>기존 카드 풀기</Link> : null}
          {fileOf("main_apkg") ? (
            <button className="is-quiet" onClick={() => void download(fileOf("main_apkg")!)}>기존 Anki 덱 받기</button>
          ) : null}
        </details>
      ) : null}
      <CardFixLinks lecture={lecture} counts={detail.cardReview} />
      <PanelGroup
        tone="plain"
        title={`${lecture.subject} 블럭 덱 받기`}
        note="현재까지 나온 것 한 파일로"
        fold
        onOpenChange={setShowBundles}
      >
        <div className="panel-bundles">
          {bundles.decks ? (
            (["pre", "main"] as const).map((kind) => (
              <BundleButton
                key={kind}
                scope={{ kind: "subject", subject: lecture.subject }}
                kind={kind}
                decks={decksIn(bundles.decks ?? [], { kind: "subject", subject: lecture.subject }, kind)}
                onDone={bundles.reload}
              />
            ))
          ) : (
            bundles.error ? <p className="panel-hint is-error" role="alert">{bundles.error}{" "}<button onClick={bundles.reload}>다시 시도</button></p>
              : <p className="panel-hint">덱 목록을 불러오는 중…</p>
          )}
        </div>
      </PanelGroup>
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
    [previewNotesLabel(detail), detail.files.find((file) => file.kind === "notes_prev")],
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
