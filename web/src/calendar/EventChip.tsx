import type { LectureRef } from "../types";
import { entryPhase, hasTodo, prequizDone, type CalendarEntry, type LecturePhase } from "./entries";

/** 강의 상세는 새 창이다. 캘린더를 잃지 않고 자료를 여닫으라는 뜻이다. */
export function lectureHref(lecture: Pick<LectureRef, "subject" | "runId">) {
  return `/lectures/${encodeURIComponent(lecture.subject)}/${encodeURIComponent(lecture.runId)}`;
}

/**
 * 강의 전에 그릴 것과 후에 그릴 것.
 *
 * 예습은 강의 전에만, 필기와 본덱은 강의 후에만 할 일이다. 셋을 늘 함께
 * 찍으면 점은 "무엇이 올라와 있나"를 말할 뿐이고, 그건 칸의 진하기가 이미
 * 말하고 있다. 시점으로 가르면 남은 점이 전부 *지금 눌러서 쓸 것*이 된다.
 *
 * 그래서 한 번에 최대 두 개다. 강의 전 두 점과 후 두 점이 모양을 나눠 써도
 * 한 화면에 같이 서지 않으므로 헷갈릴 자리가 없다.
 */
const phaseMarks: Record<LecturePhase, [keyof LectureRef["marks"], string][]> = {
  before: [
    ["preview", "예습"],
    ["prequiz", "예습퀴즈"],
  ],
  after: [
    ["notes", "필기"],
    ["quiz", "본퀴즈"],
  ],
};

/**
 * 점 둘.
 *
 * 강조색은 "네가 열어 볼 것이 있다"는 뜻으로만 쓴다. 나머지 화면이 전부
 * 무채색인 이유가 이것이다 — 색이 여러 뜻을 가지면 아무 뜻도 없어진다.
 *
 * **예습퀴즈 점만 얼마나 했는지까지 말한다.** 채운 만큼이 푼 비율이고, 다 풀면
 * 꽉 찬다. 나머지 셋은 있다/없다다 — 덱은 apkg로 나가 Anki에서 풀리므로
 * 서버가 "했다"를 볼 방법이 없다.
 */
export function Marks({ lecture, phase }: { lecture: LectureRef; phase: LecturePhase }) {
  const on = phaseMarks[phase].filter(([key]) => lecture.marks[key]);
  if (!on.length) return null;

  const progress = lecture.prequizProgress;
  const label = on
    .map(([key, name]) =>
      key === "prequiz" && progress ? `${name} ${progress.answered}/${progress.total}` : name,
    )
    .join("·");

  return (
    <span className="chip-marks" aria-label={`${label} 있음`}>
      {on.map(([key]) => {
        if (key !== "prequiz") return <i key={key} className={`chip-dot is-${key}`} />;
        // 잴 것이 없으면(덱만 있고 웹 문항이 없다) 비율을 그리지 않는다.
        // 0%로 그리면 "안 풀었다"로 읽히는데 실은 풀 자리가 없는 것이다.
        if (!progress) return <i key={key} className="chip-dot is-prequiz" />;
        const ratio = Math.round((progress.answered / progress.total) * 100);
        return (
          <i
            key={key}
            className={prequizDone(lecture) ? "chip-dot is-prequiz is-done" : "chip-dot is-prequiz"}
            style={{ ["--fill" as string]: `${ratio}%` }}
          />
        );
      })}
    </span>
  );
}

/**
 * 캘린더 한 칸.
 *
 * **자료가 있든 없든 버튼이다.** 어느 칸을 눌러도 패널이 열리고, 거기서 자료를
 * 주거나 아직 없다고 말한다. 자료 있는 칸만 누를 수 있게 두면 화면 대부분이
 * 죽은 사각형이 되고, 사용자는 그것을 "고장"으로 읽는다.
 */
export function EventChip({
  entry,
  compact,
  onOpen,
  active,
}: {
  entry: CalendarEntry;
  compact: boolean;
  onOpen: (entry: CalendarEntry) => void;
  active: boolean;
}) {
  const primary = entry.detail || entry.title;
  const lecture = entry.lectures[0];
  // 그릴 때마다 다시 읽는다. 강의가 끝나는 순간 점이 예습에서 복습으로 넘어가야
  // 하는데, 한 번 잡아 두면 자정까지 안 넘어간다.
  const phase = entryPhase(entry, new Date());
  // 왼쪽 띠는 범주만 진다. 할 일이 남았는지는 제목의 무게로만 말하고,
  // 무엇이 얼마나 남았는지는 아래 점이 말한다.
  const className = [
    "calendar-event",
    `is-${entry.category}`,
    hasTodo(entry, phase) ? "state-todo" : "",
    compact ? "is-compact" : "",
    // `is-active`가 아니다 — base.css의 `button.is-active`가 토글 버튼용으로 그
    // 이름을 이미 쓰고 있어서, 칸에 붙이면 계열과 무관하게 강조색 배경·글자색이
    // 딸려 온다. 눌린 칸이 전부 파래지던 것이 그것이었다.
    active ? "is-open" : "",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <button type="button" className={className} title={primary} onClick={() => onOpen(entry)}>
      <strong className="calendar-event-primary">{primary}</strong>
      {/* 교수와 과목은 한 겹으로 싼다. 칸이 낮으면 CSS가 이 겹을 한 줄로 눕히고
          넉넉하면 `display: contents`로 풀어 예전처럼 두 줄로 편다. 합치면 줄
          하나(13px)가 예산에서 빠져서, 같은 칸 높이에서 과목이 더 오래 산다. */}
      {!compact && (entry.professor || (entry.detail && entry.course)) ? (
        <small className="calendar-event-meta">
          {entry.professor ? <span className="calendar-event-professor">{entry.professor}</span> : null}
          {entry.detail && entry.course ? <span className="calendar-event-series">{entry.course}</span> : null}
        </small>
      ) : null}
      {/* 한 교시에 여러 강의가 열릴 때(선택형 과목)는 몇 개인지만 찍는다.
          어느 것을 열지는 패널에서 고른다 — 칸이 그것을 담기에는 좁다. */}
      {entry.lectures.length > 1 ? (
        <span className="chip-count">{entry.lectures.length}</span>
      ) : lecture ? (
        <Marks lecture={lecture} phase={phase} />
      ) : null}
    </button>
  );
}
