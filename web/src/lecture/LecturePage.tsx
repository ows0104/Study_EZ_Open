import { useCallback, useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api, openSignedFile } from "../api";
import type { LectureDetail, LectureFile } from "../types";
import { PreQuiz } from "./PreQuiz";
import { Stem } from "./Stem";

/**
 * 강의 상세. 순서가 공부 순서다.
 *
 *   작년 강의록 → 예습 열기 → Pre-Quiz → 올해 강의록 → Main-Quiz
 *
 * 강의 전에 작년 것으로 예습하고, 예습한 것을 확인하고, 강의를 듣고, 시험
 * 대비를 한다. 화면이 그 순서대로 놓여 있어야 무엇을 먼저 할지 묻지 않는다.
 */
export function LecturePage() {
  const params = useParams<{ subject: string; runId: string }>();
  const subject = params.subject ?? "";
  const runId = params.runId ?? "";
  const [detail, setDetail] = useState<LectureDetail | null>(null);
  const [error, setError] = useState("");
  const [solving, setSolving] = useState(false);

  const load = useCallback(() => {
    api<LectureDetail>(`/api/lectures/${encodeURIComponent(subject)}/${encodeURIComponent(runId)}`)
      .then(setDetail)
      .catch((cause: Error) => setError(cause.message));
  }, [subject, runId]);

  useEffect(load, [load]);

  useEffect(() => {
    if (detail) document.title = `${detail.title} · Study_EZ`;
  }, [detail]);

  if (error) return <p className="notice is-error">{error}</p>;
  if (!detail) return <p className="notice">불러오는 중…</p>;

  const fileOf = (kind: LectureFile["kind"]) => detail.files.find((file) => file.kind === kind);
  const preApkg = fileOf("pre_apkg");
  const quiz = detail.prequiz;

  async function open(file: LectureFile) {
    try {
      await openSignedFile(
        `/api/lectures/${encodeURIComponent(subject)}/${encodeURIComponent(runId)}/files/${file.id}`,
      );
    } catch (cause) {
      setError((cause as Error).message);
    }
  }

  const fileButton = (kind: LectureFile["kind"], label: string) => (
    <FileButton key={kind} file={fileOf(kind)} label={label} onOpen={open} />
  );

  return (
    <article className="lecture">
      <header className="lecture-head">
        <p className="lecture-crumb">
          {detail.course || detail.subject} · {detail.date} · {detail.slot}교시 {detail.startTime}
        </p>
        <h1>{detail.title}</h1>
        <p className="lecture-meta">
          {detail.professors.join(", ") || "교수 미상"}
          {detail.author ? ` · 필기 ${detail.author}${detail.version ? `v${detail.version}` : ""}` : ""}
        </p>
      </header>

      {detail.runMeta ? <AdminNotice runMeta={detail.runMeta} /> : null}

      <section className="lecture-section">
        <h2>강의 전</h2>
        {fileButton("notes_prev", "작년 강의록")}
        {detail.preview?.shareUrl ? (
          <a className="resource" href={detail.preview.shareUrl} target="_blank" rel="noreferrer">
            <strong>예습 열기</strong>
            <small>{detail.preview.provider} 대화</small>
          </a>
        ) : (
          <div className="resource is-empty">예습 링크 — 아직 없습니다</div>
        )}

        {quiz ? (
          solving ? (
            <PreQuiz
              subject={subject}
              runId={runId}
              onFinished={() => {
                setSolving(false);
                load();
              }}
            />
          ) : (
            <div className="resource-group">
              <button className="resource is-primary" onClick={() => setSolving(true)}>
                <strong>Pre-Quiz 풀기</strong>
                <small>
                  {quiz.itemCount}문항
                  {quiz.answered ? ` · ${quiz.answered}개 풀었고 ${quiz.correct}개 맞았습니다` : ""}
                </small>
              </button>
              {preApkg ? (
                <button className="resource is-quiet" onClick={() => open(preApkg)}>
                  <strong>Pre-Quiz 덱 내려받기</strong>
                  <small>{preApkg.filename}</small>
                </button>
              ) : null}
            </div>
          )
        ) : (
          <div className="resource is-empty">Pre-Quiz — 아직 없습니다</div>
        )}
      </section>

      {quiz && quiz.missed.length ? (
        <section className="missed">
          <h2>오늘 놓친 것 {quiz.missed.length}개</h2>
          {/* 틀린 문항이 그 강의의 청취 목표다. 이 목록이 있으라고 웹에서 푸는
              것이지, 채점 결과가 남지 않으면 apkg로 충분했다. */}
          <ol>
            {quiz.missed.map((entry) => (
              <li key={entry.itemId}>
                <p className="missed-stem">
                  <Stem text={entry.stem} />
                </p>
                {entry.retrievalTarget ? <p className="missed-target">{entry.retrievalTarget}</p> : null}
                {entry.examHit ? <span className="badge">기출</span> : null}
              </li>
            ))}
          </ol>
        </section>
      ) : null}

      <section className="lecture-section">
        <h2>강의 후</h2>
        {fileButton("notes_current", "올해 강의록")}
        {fileButton("main_apkg", "Main-Quiz 덱")}
      </section>
    </article>
  );
}

function FileButton({
  file,
  label,
  onOpen,
}: {
  file: LectureFile | undefined;
  label: string;
  onOpen: (file: LectureFile) => void;
}) {
  // 아직 없는 것도 자리를 남긴다. 목록에서 빠지면 "없다"와 "이 강의에는 원래
  // 해당 없다"를 구분할 수 없다.
  if (!file) return <div className="resource is-empty">{label} — 아직 없습니다</div>;
  return (
    <button className="resource" onClick={() => onOpen(file)}>
      <strong>{label}</strong>
      <small>
        {file.filename} · {(file.sizeBytes / 1024 / 1024).toFixed(1)}MB
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
