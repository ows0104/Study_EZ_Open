import { useCallback, useEffect, useState } from "react";
import { useNoteLecture } from "../notes/noteLecture";
import { useParams } from "react-router-dom";
import { api } from "../api";
import { lectureHref } from "../links";
import type { LectureDetail } from "../types/lectures";
import type { QuizKind } from "../types/quiz";
import { Missed } from "./Missed";
import { Quiz } from "./Quiz";
import { PreQuiz } from "./PreQuiz";

/** 갈래마다 다른 것은 이름과 다음에 확인할 자료뿐이다. */
const LOOK: Record<QuizKind, { title: string; next: string }> = {
  pre: {
    title: "Pre-Quiz",
    next: "필기와 Main-Quiz",
  },
  main: {
    title: "기존 Main-Quiz",
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
 * **오늘 낼 카드가 없을 때도 아래가 붙는다**(2026-09-18). 그 전까지 「다 찍었다」는
 * 마지막 카드를 지났다는 뜻이었는데, 일정이 도는 지금은 「오늘 몫을 끝냈다」다.
 *
 * **여기 쌓이는 진행과 덱의 진행은 여전히 다른 것이다.** 웹은 웹에서 찍은 것을
 * 들고, apkg를 받아 간 사람의 안키는 자기 것을 든다 — 둘을 더해 「몇 번 봤다」로
 * 읽으면 안 된다. 예습 웹은 1회 확인이며, 기존 Main 웹의 반복 일정도 Anki와 별개다.
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
  useNoteLecture(detail?.title);

  // 놓친 것은 서버가 고른다. 마지막 카드를 찍은 뒤에 다시 불러야 채워져 온다.
  const onDone = useCallback(
    (done: boolean) => {
      setFinished(done);
      if (done) load();
    },
    [load],
  );

  const quiz = kind === "pre" ? detail?.prequiz : detail?.mainquiz;

  // 2026-11 개편: 예습은 새 Main-Quiz처럼 좌측 메뉴 안에서 푼다(머리줄·진행 막대·카드·아래 독).
  if (kind === "pre") return (
    <article className="prequiz-page">
      {error ? <p className="notice is-error">{error}</p> : null}
      <PreQuiz key={`${subject}/${runId}`} subject={subject} runId={runId} title={detail?.title} onDone={onDone} />
    </article>
  );

  return (
    <article className="lecture">
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
        <Quiz key={`${subject}/${runId}`} kind="main" subject={subject} runId={runId} onDone={onDone} />
      </section>

      {/* 다 찍은 뒤에 붙는 것들은 읽는 글이다. 푸는 창이 넓어졌다고 이것까지
          늘리면 한 줄이 길어져서 읽기만 나빠진다. */}
      {finished ? (
        <div className="prequiz-narrow">
          <Missed items={quiz?.missed ?? []} />

          <section className="lecture-section">
            <h2>다음</h2>
            <a className="resource" href={lectureHref({ subject, runId })}>
              <strong>강의 화면 열기</strong>
              <small>{look.next}</small>
            </a>
          </section>
        </div>
      ) : null}
    </article>
  );
}
