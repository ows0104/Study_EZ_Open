import { useCallback, useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api, downloadSignedFile } from "../api";
import { lectureHref } from "../links";
import type { LectureDetail, LectureFile } from "../types/lectures";
import type { QuizKind } from "../types/quiz";
import { Missed } from "./Missed";
import { Quiz } from "./Quiz";

/** 갈래마다 다른 것은 이름과 덱과 「다음」의 문구뿐이다. */
const LOOK: Record<QuizKind, { title: string; deck: LectureFile["kind"]; deckNote: string; next: string }> = {
  pre: {
    title: "Pre-Quiz",
    deck: "pre_apkg",
    deckNote: "그림 카드까지 들어 있습니다",
    next: "필기와 Main-Quiz 덱",
  },
  main: {
    title: "기존 Main-Quiz",
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
 * **오늘 낼 카드가 없을 때도 아래가 붙는다**(2026-09-18). 그 전까지 「다 찍었다」는
 * 마지막 카드를 지났다는 뜻이었는데, 일정이 도는 지금은 「오늘 몫을 끝냈다」다.
 *
 * **여기 쌓이는 진행과 덱의 진행은 여전히 다른 것이다.** 웹은 웹에서 찍은 것을
 * 들고, apkg를 받아 간 사람의 안키는 자기 것을 든다 — 둘을 더해 「몇 번 봤다」로
 * 읽으면 안 된다. 같은 SM-2로 돌지만 두 일정은 서로를 모른다.
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
            {/* 덱은 안키에서 돌릴 사람의 것이다. 웹에도 일정이 생겼으므로
                「반복하려면 덱」이 아니라 **「안키에서 보려면 덱」**이다. */}
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
