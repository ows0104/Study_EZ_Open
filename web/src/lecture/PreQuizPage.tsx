import { useCallback, useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api, downloadSignedFile } from "../api";
import { lectureHref } from "../links";
import type { LectureDetail, LectureFile } from "../types";
import { Missed } from "./Missed";
import { PreQuiz } from "./PreQuiz";

/**
 * Pre-Quiz 전용 창.
 *
 * 강의 화면 안에서 풀던 것을 밖으로 냈다. 푸는 동안 화면에 있어야 하는 것은
 * 문항과 답과 슬라이드뿐인데, 강의 화면에는 그 위아래로 필기·덱·예습 링크가
 * 서 있다. 캘린더에서 곧장 열리는 것은 덤이다.
 *
 * 다 찍고 나서야 아래가 붙는다 — 놓친 것, 그리고 다음에 할 것(덱·강의 화면).
 * 푸는 동안 그것들이 보이면 답을 펴기 전에 다른 데를 누르게 된다.
 */
export function PreQuizPage() {
  const params = useParams<{ subject: string; runId: string }>();
  const subject = params.subject ?? "";
  const runId = params.runId ?? "";
  const [detail, setDetail] = useState<LectureDetail | null>(null);
  const [error, setError] = useState("");
  const [finished, setFinished] = useState(false);

  const load = useCallback(() => {
    api<LectureDetail>(`/api/lectures/${encodeURIComponent(subject)}/${encodeURIComponent(runId)}`)
      .then(setDetail)
      .catch((cause: Error) => setError(cause.message));
  }, [subject, runId]);

  useEffect(load, [load]);

  useEffect(() => {
    if (detail) document.title = `Pre-Quiz · ${detail.title}`;
  }, [detail]);

  // 놓친 것은 서버가 고른다. 마지막 카드를 찍은 뒤에 다시 불러야 채워져 온다.
  const onDone = useCallback(
    (done: boolean) => {
      setFinished(done);
      if (done) load();
    },
    [load],
  );

  async function download(file: LectureFile) {
    try {
      await downloadSignedFile(
        `/api/lectures/${encodeURIComponent(subject)}/${encodeURIComponent(runId)}/files/${file.id}`,
        file.filename,
      );
    } catch (cause) {
      setError((cause as Error).message);
    }
  }

  const preApkg = detail?.files.find((file) => file.kind === "pre_apkg");
  const quiz = detail?.prequiz;

  return (
    <article className="lecture">
      {/* 강의 정보는 머리글 한 줄로 족하다. 여기는 푸는 창이다. */}
      {detail ? (
        <header className="lecture-head">
          <p className="lecture-crumb">
            <span>{detail.course || detail.subject}</span>
            <i aria-hidden="true" />
            <time>{detail.date}</time>
            <i aria-hidden="true" />
            <span>Pre-Quiz</span>
          </p>
          <h1>{detail.title}</h1>
        </header>
      ) : null}

      {error ? <p className="notice is-error">{error}</p> : null}

      {/* 강의 상세를 기다리지 않는다. 카드는 자기 요청으로 따로 온다. */}
      <section className="lecture-section">
        <PreQuiz subject={subject} runId={runId} onDone={onDone} />
      </section>

      {finished ? (
        <>
          <Missed items={quiz?.missed ?? []} />

          <section className="lecture-section">
            <h2>다음</h2>
            {/* 웹은 한 번 훑는 자리다. 반복은 Anki가 한다 — 3패스가 그 덱에서 돈다. */}
            {preApkg ? (
              <button className="resource is-download" onClick={() => download(preApkg)}>
                <strong>Pre-Quiz 덱 내려받기</strong>
                <small>
                  {preApkg.filename} · {(preApkg.sizeBytes / 1024 / 1024).toFixed(1)}MB · 그림 카드까지 들어 있습니다
                </small>
              </button>
            ) : null}
            <a className="resource" href={lectureHref({ subject, runId })} target="_blank" rel="noreferrer">
              <strong>강의 화면 열기</strong>
              <small>필기와 Main-Quiz 덱</small>
            </a>
          </section>
        </>
      ) : null}
    </article>
  );
}
