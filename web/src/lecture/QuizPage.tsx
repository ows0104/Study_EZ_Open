import { useCallback, useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api, downloadSignedFile } from "../api";
import { lectureHref } from "../links";
import type { LectureDetail, LectureFile, QuizKind } from "../types";
import { Missed } from "./Missed";
import { Quiz } from "./Quiz";

/** 갈래마다 다른 것은 이름과 덱과 「다음」의 문구뿐이다. */
const LOOK: Record<QuizKind, { title: string; deck: LectureFile["kind"]; deckNote: string; next: string }> = {
  pre: {
    title: "Pre-Quiz",
    deck: "pre_apkg",
    // 웹은 한 번 훑는 자리다. 반복은 Anki가 한다 — 3패스가 그 덱에서 돈다.
    deckNote: "그림 카드까지 들어 있습니다",
    next: "필기와 Main-Quiz 덱",
  },
  main: {
    title: "Main-Quiz",
    deck: "main_apkg",
    deckNote: "그림 카드까지 들어 있습니다",
    next: "필기와 예습 링크",
  },
};

/**
 * 웹 풀이 전용 창. **예습·복습 둘 다 이 화면이다.**
 *
 * 강의 화면 안에서 풀던 것을 밖으로 냈다. 푸는 동안 화면에 있어야 하는 것은
 * 문항과 답과 슬라이드뿐인데, 강의 화면에는 그 위아래로 필기·덱·예습 링크가
 * 서 있다. 캘린더에서 곧장 열리는 것은 덤이다.
 *
 * 다 찍고 나서야 아래가 붙는다 — 놓친 것, 그리고 다음에 할 것(덱·강의 화면).
 * 푸는 동안 그것들이 보이면 답을 펴기 전에 다른 데를 누르게 된다.
 *
 * **복습에서 여기 쌓이는 것은 웹에서 푼 몫뿐이다.** 그 덱의 진행은 Anki가 든다.
 */
export function QuizPage({ kind }: { kind: QuizKind }) {
  const look = LOOK[kind];
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
    if (detail) document.title = `${look.title} · ${detail.title}`;
  }, [detail, look.title]);

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

  const apkg = detail?.files.find((file) => file.kind === look.deck);
  const quiz = kind === "pre" ? detail?.prequiz : detail?.mainquiz;

  return (
    <article className="lecture">
      {/* 강의 정보는 머리글 한 줄로 족하다. 여기는 푸는 창이다. */}
      {detail ? (
        <header className="lecture-head prequiz-narrow">
          <p className="lecture-crumb">
            <span>{detail.course || detail.subject}</span>
            <i aria-hidden="true" />
            <time>{detail.date}</time>
            <i aria-hidden="true" />
            <span>{look.title}</span>
          </p>
          <h1>{detail.title}</h1>
        </header>
      ) : null}

      {error ? <p className="notice is-error">{error}</p> : null}

      {/* 강의 상세를 기다리지 않는다. 카드는 자기 요청으로 따로 온다. */}
      <section className="lecture-section">
        <Quiz kind={kind} subject={subject} runId={runId} onDone={onDone} />
      </section>

      {/* 다 찍은 뒤에 붙는 것들은 읽는 글이다. 푸는 창이 넓어졌다고 이것까지
          늘리면 한 줄이 길어져서 읽기만 나빠진다. */}
      {finished ? (
        <div className="prequiz-narrow">
          <Missed items={quiz?.missed ?? []} />

          <section className="lecture-section">
            <h2>다음</h2>
            {/* 웹은 한 번 훑는 자리다. 반복은 Anki가 한다 — 3패스가 그 덱에서 돈다. */}
            {apkg ? (
              <button className="resource is-download" onClick={() => download(apkg)}>
                <strong>{look.title} 덱 내려받기</strong>
                <small>
                  {apkg.filename} · {(apkg.sizeBytes / 1024 / 1024).toFixed(1)}MB · {look.deckNote}
                </small>
              </button>
            ) : null}
            <a className="resource" href={lectureHref({ subject, runId })} target="_blank" rel="noreferrer">
              <strong>강의 화면 열기</strong>
              <small>{look.next}</small>
            </a>
          </section>
        </div>
      ) : null}
    </article>
  );
}
