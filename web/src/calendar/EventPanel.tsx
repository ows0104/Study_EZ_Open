import { useEffect, useRef, useState } from "react";
import { BankPanel } from "../bank/BankPanel";
import { api, downloadSignedFile, openSignedFile } from "../api";
import { BundleButton } from "../bundle/BundleButton";
import { decksIn, type BundleDeck } from "../bundle/decks";
import { usePreviewVersion } from "../bridge/previewBridge";
import { lectureHref, legacyMainHref, quizHref, quizWindow } from "../links";
import { type LectureDetail, type LectureFile, type LectureRef } from "../types/lectures";
import { categoryLabel, type CalendarEntry } from "./entries";
import { DeckSlot } from "./DeckSlot";
import { cardsHash } from "../lecture/LectureCards";
import { ActionCard, fileSize, PanelGroup } from "./panelShared";
import { PreviewAction } from "./PreviewAction";
import { ReviewAction } from "./ReviewAction";
import { LectureMastery } from "../lecture/LectureMastery";

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
  onClose,
  bundleDecks,
  onBundleDone,
}: {
  entry: CalendarEntry;
  onClose: () => void;
  /** 덱이 어디 있고 무엇을 받아 갔나. **부모가 한 번 받아 내려준다** — 패널마다
   *  부르면 칸을 갈아탈 때마다 학기 전체를 다시 받는다. 아직 안 왔으면 `null`. */
  bundleDecks: BundleDeck[] | null;
  onBundleDone: () => void;
}) {
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
            <KeyActions
              lecture={lecture}
              detail={detail}
              bundleDecks={bundleDecks}
              onBundleDone={onBundleDone}
            />
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

        {detail ? <LectureMastery value={detail.mastery} /> : null}

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
function KeyActions({
  lecture,
  detail,
  bundleDecks,
  onBundleDone,
}: {
  lecture: LectureRef;
  detail: LectureDetail;
  bundleDecks: BundleDeck[] | null;
  onBundleDone: () => void;
}) {
  const base = `/api/lectures/${encodeURIComponent(lecture.subject)}/${encodeURIComponent(lecture.runId)}`;
  const [error, setError] = useState("");
  const fileOf = (kind: LectureFile["kind"]) => detail.files.find((file) => file.kind === kind);

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

  /**
   * 덩어리의 앞칸 — 「웹에서 풀기」. 문항이 없으면 아예 안 세운다(덱만 남는다).
   *
   * 누르면 그 갈래의 전용 창이 열린다. 캘린더도 이 패널도 그대로 남는다.
   * 문항 수는 이름 옆이 말한다 — 덱 칸에서 되풀이하면 덱의 장수처럼 읽히는데,
   * 덱에는 그림 카드까지 들어 있어 언제나 더 많다.
   */
  function webSolve(kind: "pre" | "main", progress: LectureDetail["prequiz"]) {
    if (!progress) return undefined;
    return (tools: React.ReactNode) => (
      <ActionCard
        shape="is-lead"
        hit={
          <a className="panel-action-hit" href={quizHref(kind, lecture)} target={quizWindow(kind, lecture)}>
            <strong>웹에서 풀기</strong>
            <small>
              {/* 일정이 도는 자리라 「몇 장 있나」보다 「오늘 뭘 해야 하나」가
                  먼저다(2026-09-18). 강의 상세의 그 줄과 같은 규칙이다. */}
              {progress.answered
                ? progress.due
                  ? `오늘 낼 카드 ${progress.due}장`
                  : `오늘 몫 완료 · ${progress.later}장 대기`
                : `${progress.itemCount}장`}
            </small>
          </a>
        }
        tools={tools}
      />
    );
  }

  return (
    <div className="event-panel-actions">
      <PreviewAction lecture={lecture} detail={detail} base={base} onError={setError} />

      {/* **웹 풀이와 덱을 한 덩어리로 붙였다(2026-08-31 관리자 지시).** 둘은 한
          가지를 하는 두 길인데 — 여기서 풀 것이냐, Anki로 가져갈 것이냐 —
          위아래 두 줄로 세워 두니 서로 다른 것으로 읽혔다.

          「다시 만들기」는 덱의 것이지만 넓은 왼쪽 칸이 든다 — 덱 칸은 이름과
          용량으로 한 줄이 찬다(관리자 지시도 그 자리였다). */}
      <PanelGroup tone="pre" title="Pre-Quiz" note="강의 전 예습">
        <DeckSlot
          kind="pre"
          label="덱"
          file={fileOf("pre_apkg")}
          lecture={lecture}
          onDownload={download}
          before={webSolve("pre", detail.prequiz)}
          blocked={
            detail.preview?.shareUrl
              ? undefined
              : { short: "예습 링크 대기", why: "예습 링크를 먼저 저장하세요. Pre-Quiz는 그 대화로 만듭니다." }
          }
        />
      </PanelGroup>

      <ReviewAction lecture={lecture} detail={detail} base={base} onError={setError} />
      <BankPanel lecture={lecture} detail={detail} />
      {detail.mainquiz || fileOf("main_apkg") ? (
        <details className="panel-hint legacy-main">
          <summary>기존 Main-Quiz 자료</summary>
          {detail.mainquiz ? <a href={legacyMainHref(lecture)} target="_blank" rel="noreferrer">기존 카드 풀기</a> : null}
          {fileOf("main_apkg") ? (
            <button className="is-quiet" onClick={() => void download(fileOf("main_apkg")!)}>기존 Anki 덱 받기</button>
          ) : null}
        </details>
      ) : null}

      <CardFixLinks lecture={lecture} counts={detail.cardReview} />

      {/* **블럭 전체를 한 파일로**(2026-09-15 관리자 지시). 블럭은 과목 하나다 —
          「감염의 기초」가 기생충학과 미생물학 둘로 갈려 서는 것이 이 학기의
          실제 모양이고(`runner/ahead.py` 의 `_block_from`·`_block_until`),
          덱 나무의 맨 위 마디도 과목이다.

          **강의 패널에 두는 것이 억지가 아닌 이유는 여기가 과목을 아는 자리라서다.**
          캘린더 칸은 시간표 이름(「감염의 기초 7」)을 들고 있고 과목 이름은 강의가
          든다. 한 번 눌러 연 사람은 이미 그 과목을 보고 있다.

          **접힌 채로 서고 회색을 진다(2026-09-18 관리자 지시 — 의도보다 눈에
          띈다).** 위의 Pre-Quiz·Main-Quiz 가 이 패널이 하라는 일이고 이것은 그
          다음이다. 그런데 바로 위 두 칸과 같은 teal·indigo 를 칠하고 펼쳐져
          있으니 「덱 받기」가 한 화면에 네 번 나온 것처럼 읽혔다.

          **이름이 「블럭 전체」에서 「현재까지」로 바뀐 것도 같은 지시다.**
          담기는 것은 처음부터 지금까지 구워진 편이고 — 블럭이 끝나기 전이면
          「전체」가 아직 없다 — 앞으로 나올 편은 다시 눌러야 온다. */}
      <PanelGroup
        tone="plain"
        title={`${lecture.subject} 블럭 덱 받기`}
        note="현재까지 나온 것 한 파일로"
        fold
      >
        <div className="panel-bundles">
          {bundleDecks ? (
            (["pre", "main"] as const).map((kind) => (
              <BundleButton
                key={kind}
                scope={{ kind: "subject", subject: lecture.subject }}
                kind={kind}
                decks={decksIn(bundleDecks, { kind: "subject", subject: lecture.subject }, kind)}
                onDone={onBundleDone}
              />
            ))
          ) : (
            <p className="panel-hint">덱 목록을 불러오는 중…</p>
          )}
        </div>
      </PanelGroup>

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
