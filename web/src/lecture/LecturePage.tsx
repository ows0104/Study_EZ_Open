import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, downloadSignedFile, openSignedFile } from "../api";
import { useBankLink } from "../bank/bankBridge";
import { BankPanel } from "../bank/BankPanel";
import { ReviewAction } from "../calendar/ReviewAction";
import { bumpPreviewVersion, usePreviewLink, watchSharedLink } from "../bridge/previewBridge";
import { legacyMainHref, quizHref } from "../links";
import { previewProviderLabels, previewProviders, type LectureDetail, type LectureFile, type PreviewProvider } from "../types/lectures";
import { LectureCards } from "./LectureCards";
import { Missed } from "./Missed";
import { LectureMastery } from "./LectureMastery";
import { useMe } from "../useMe";

/**
 * 강의 상세. 순서가 공부 순서다.
 *
 *   작년 필기 → 예습 열기 → Pre-Quiz → 올해 필기 → Main-Quiz
 *
 * 강의 전에 작년 것으로 예습하고, 예습한 것을 확인하고, 강의를 듣고, 시험
 * 대비를 한다. 화면이 그 순서대로 놓여 있어야 무엇을 먼저 할지 묻지 않는다.
 */
export function LecturePage() {
  const params = useParams<{ subject: string; runId: string }>();
  const subject = params.subject ?? "";
  const runId = params.runId ?? "";
  const isAdmin = Boolean(useMe()?.isAdmin);
  const [detail, setDetail] = useState<LectureDetail | null>(null);
  const [error, setError] = useState("");

  const load = useCallback(() => {
    api<LectureDetail>(`/api/lectures/${encodeURIComponent(subject)}/${encodeURIComponent(runId)}`)
      .then(setDetail)
      .catch((cause: Error) => setError(cause.message));
  }, [subject, runId]);

  useEffect(load, [load]);
  useEffect(() => {
    window.addEventListener("focus", load);
    return () => window.removeEventListener("focus", load);
  }, [load]);

  // Quiz Bank 답 본문도 같은 자리에서 받는다(관리자). 확장이 이 탭으로 밀어 준다.
  useBankLink();
  usePreviewLink(
    useCallback(async ({ lectureId, kind, url }) => {
      const [linkSubject, linkRunId] = lectureId.split("/");
      if (!linkSubject || !linkRunId) return;
      const shared = kind.endsWith("_share");
      const review = kind.endsWith("_review");
      const provider = (shared ? kind.slice(0, -6) : review ? kind.slice(0, -7) : kind) as PreviewProvider;
      if (!previewProviders.includes(provider)) return;
      const path = `${encodeURIComponent(linkSubject)}/${encodeURIComponent(linkRunId)}`;
      await api(shared ? `/api/admin/lectures/${path}/preview` : `/api/lectures/${path}/${review ? "my-review" : "my-preview"}`, {
        method: "PUT",
        body: JSON.stringify(shared ? { provider, shareUrl: url } : { provider, conversationUrl: url }),
      });
      bumpPreviewVersion();
      load();
    }, [load]),
  );

  useEffect(() => {
    if (detail) document.title = `${detail.title} · Study_EZ`;
  }, [detail]);

  if (error) return <p className="notice is-error">{error}</p>;
  if (!detail) return <p className="notice">불러오는 중…</p>;

  const fileOf = (kind: LectureFile["kind"]) => detail.files.find((file) => file.kind === kind);
  const quiz = detail.prequiz;

  const fileUrl = (file: LectureFile) =>
    `/api/lectures/${encodeURIComponent(subject)}/${encodeURIComponent(runId)}/files/${file.id}`;

  // 필기는 PDF라 브라우저가 그대로 보여 줄 수 있다. `inline=1`이 없으면 서버가
  // 첨부로 서명해 줘서 탭이 뜨자마자 내려받기로 바뀐다.
  async function open(file: LectureFile) {
    try {
      await openSignedFile(`${fileUrl(file)}?inline=1`);
    } catch (cause) {
      setError((cause as Error).message);
    }
  }

  // 덱은 보는 것이 아니라 받는 것이다. 새 탭으로 열면 그 탭이 곧바로 내려받기로
  // 바뀌면서 빈 탭만 남는다.
  async function download(file: LectureFile) {
    try {
      await downloadSignedFile(fileUrl(file), file.filename);
    } catch (cause) {
      setError((cause as Error).message);
    }
  }

  const fileButton = (kind: LectureFile["kind"], label: string, extra = "") => {
    const deck = kind === "pre_apkg" || kind === "main_apkg";
    return (
      <FileButton
        key={kind}
        file={fileOf(kind)}
        label={label}
        onPick={deck ? download : open}
        hint={deck ? "내려받기" : ""}
        className={`${deck ? "is-download" : ""} ${extra}`.trim()}
      />
    );
  };

  return (
    <article className="lecture">
      <header className="lecture-head">
        <p className="lecture-crumb">
          <span>{detail.course || detail.subject}</span>
          <i aria-hidden="true" />
          <time>{detail.date}</time>
          <i aria-hidden="true" />
          <span>
            {detail.slot}교시 <time>{detail.startTime}</time>
          </span>
        </p>
        <h1>{detail.title}</h1>
        <p className="lecture-meta">
          {detail.professors.join(", ") || "교수 미상"}
          {detail.author ? ` · 필기 ${detail.author}${detail.version ? `v${detail.version}` : ""}` : ""}
        </p>
      </header>

      {detail.runMeta ? <AdminNotice runMeta={detail.runMeta} /> : null}
      <LectureMastery value={detail.mastery} />

      <section className="lecture-section">
        <h2>강의 전</h2>
        {fileButton("notes_prev", "작년 필기")}
        <PreviewResource detail={detail} />

        {/* 같은 탭에서 웹 풀이 화면으로 이동한다.

            **덱이 기본이던 것을 뒤집었다(2026-08-23 관리자 지시).** 받을 사람은
            아래 줄에서 받는다 — 그림 카드까지 들어 있어 덱이 언제나 더 크다.

            2026-09-18부터 웹에도 망각곡선이 있어서, 이 줄은 **오늘 낼 카드가
            몇 장인지**를 말한다. 장수만 적던 자리에 그것을 적는 이유는, 일정이
            도는 제품에서 사람이 묻는 것이 「몇 장이 있나」가 아니라 「오늘 뭘
            해야 하나」이기 때문이다. */}
        {quiz ? (
          <Link
            className="resource is-primary"
            to={quizHref("pre", { subject, runId })}
          >
            <strong>Pre-Quiz 풀기</strong>
            <small>{quizNote(quiz)}</small>
          </Link>
        ) : null}
        {isAdmin ? fileButton("pre_apkg", "Pre-Quiz 덱", "is-secondary") : null}
      </section>

      {/* 예습에서 표시한 질문은 수업 때 다시 열어볼 수 있도록 남긴다. */}
      <Missed preview items={quiz?.missed ?? []} />

      <section className="lecture-section">
        <h2>강의 후</h2>
        {fileButton("notes_current", "올해 필기")}
        <ReviewAction lecture={{ subject, runId }} detail={detail}
          base={`/api/lectures/${encodeURIComponent(subject)}/${encodeURIComponent(runId)}`} onError={setError} />
        <BankPanel lecture={{ subject, runId }} detail={detail} />
        {detail.mainquiz || isAdmin && detail.files.some((file) => file.kind === "main_apkg") ? (
          <details className="legacy-main">
            <summary>기존 Main-Quiz 자료</summary>
            {detail.mainquiz ? (
              <Link className="resource" to={legacyMainHref({ subject, runId })}>
                <strong>기존 카드 풀기</strong>
                <small>이전에 학습한 일정과 기록을 이어갑니다.</small>
              </Link>
            ) : null}
            {isAdmin ? fileButton("main_apkg", "기존 Main-Quiz Anki 덱") : null}
          </details>
        ) : null}
      </section>

      {/* 관리자에게만 온다(`cardReview`). 사이드 패널의 「카드 고치기」가 여기로
          보낸다 — 2026-09-23 관리자 지시. */}
      {detail.cardReview ? (
        <LectureCards subject={subject} runId={runId} counts={detail.cardReview} />
      ) : null}
    </article>
  );
}

/** 예습은 한 번 확인한 핵심 문항 수만 표시한다. */
function quizNote(quiz: NonNullable<LectureDetail["prequiz"]>): string {
  if (!quiz.answered) return `핵심 ${quiz.itemCount}문항 · 답과 설명을 읽고 이해를 확인해요`;
  if (quiz.answered < quiz.itemCount) return `${quiz.answered}/${quiz.itemCount}문항 확인 · 이어서 예습하기`;
  return `예습 완료 · 핵심 ${quiz.itemCount}문항 확인`;
}

/**
 * 예습. 캘린더 패널과 같은 규칙이다 — 관리자가 공유한 대화가 있으면 그것을
 * 읽고, 없어도 작년 필기만 있으면 직접 시작할 수 있다.
 */
function PreviewResource({ detail }: { detail: LectureDetail }) {
  const notesPrev = detail.files.find((file) => file.kind === "notes_prev");

  if (detail.preview?.shareUrl) {
    return (
      <a
        className="resource"
        href={detail.preview.shareUrl}
        target="_blank"
        rel="noreferrer"
        onClick={() => watchSharedLink(
          `${detail.subject}/${detail.runId}`,
          detail.preview!.provider,
          detail.preview!.shareUrl,
        )}
      >
        <strong>기본 링크 · {previewProviderLabels[detail.preview.provider]}</strong>
        <small>공통 예습 대화</small>
      </a>
    );
  }

  if (!notesPrev) return <div className="resource is-empty">예습 — 작년 필기가 올라오면 열립니다</div>;

  // 예습을 시작하는 자리는 캘린더 패널이다. 여기는 강의를 펼쳐 보는 창이라
  // 확장을 부르지 않고, 무엇을 눌러야 하는지만 말한다.
  return (
    <div className="resource is-empty">
      예습 — 캘린더에서 이 강의를 눌러 시작하세요
      <small>확장 프로그램이 작년 필기와 프롬프트를 선택한 AI에 넣어 줍니다</small>
    </div>
  );
}

function FileButton({
  file,
  label,
  onPick,
  hint = "",
  className = "",
}: {
  file: LectureFile | undefined;
  label: string;
  onPick: (file: LectureFile) => void;
  /** 파일 이름 뒤에 붙는 한 마디. 여는 것과 받는 것을 이 자리에서 가른다. */
  hint?: string;
  className?: string;
}) {
  // 아직 없는 것도 자리를 남긴다. 목록에서 빠지면 "없다"와 "이 강의에는 원래
  // 해당 없다"를 구분할 수 없다.
  if (!file) return <div className="resource is-empty">{label} — 아직 없습니다</div>;
  return (
    <button className={`resource ${className}`.trim()} onClick={() => onPick(file)}>
      <strong>{label}</strong>
      <small>
        {file.filename} · {(file.sizeBytes / 1024 / 1024).toFixed(1)}MB
        {hint ? ` · ${hint}` : ""}
      </small>
    </button>
  );
}

/** 배포해도 되는가. `review_flagged`가 0이 아니면 사람이 봐야 한다. */
function AdminNotice({ runMeta }: { runMeta: NonNullable<LectureDetail["runMeta"]> }) {
  const warnings = Object.entries(runMeta).filter(([, meta]) => meta.reviewFlagged || meta.slidesUnused);
  if (!warnings.length) return null;
  return (
    <div className="notice is-warning">
      {warnings.map(([kind, meta]) => (
        <p key={kind}>
          {kind === "main" ? "Main-Quiz" : "Pre-Quiz"}: 검토 표시 {meta.reviewFlagged}개, 안 쓰인 슬라이드{" "}
          {meta.slidesUnused}장
        </p>
      ))}
    </div>
  );
}
