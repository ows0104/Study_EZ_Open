import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api";
import { bumpPreviewVersion } from "../bridge/previewBridge";
import {
  type DeckKind,
  type LectureFile,
  type LectureRef,
  type PrequizJob,
  type RunnerBeat,
} from "../types";
import { useMe } from "../useMe";
import { fileSize, Remake, RemakeConfirm } from "./panelShared";

/**
 * 덱 한 칸. 만들어졌으면 내려받고, 아니면 러너에게 일감을 건다.
 *
 * 일감의 진행은 `/api/admin/prequiz-jobs` 가 알려 준다(서버의 `prequiz_jobs.py`).
 * `EventPanel` 에서 갈라 나왔다.
 */
/** 러너가 이 시간 안에 안 보이면 안 붙은 것으로 친다(`AdminPage`와 같은 값). */
const RUNNER_STALE_MS = 120_000;

/**
 * 열려 있는 일감 한 줄을 사람 말로. **「만드는 중」은 러너가 집어 갔을 때만 쓴다.**
 *
 * 이 자리가 한동안 상태를 안 가리고 「만드는 중」을 먼저 적은 뒤 사정을 뒤에
 * 붙였다. 그래서 아무도 안 만들고 있을 때 이렇게 나왔다 —
 *
 *     Pre-Quiz 덱 — 만드는 중 · 러너를 기다리는 중 · 러너가 안 붙어 있습니다
 *
 * 세 토막이 서로 다른 말을 하고, 그중 첫 토막이 거짓이다. 읽는 사람은 기다리면
 * 되는 줄 알고 기다린다 — 노트북을 켜야 시작되는데. 서버가 일감과 러너 상태를
 * 같이 주는 까닭이 이걸 가르라는 것이므로(`GET …/prequiz-job`), 갈라서 **한 가지만**
 * 말한다.
 *
 * `stage`는 러너가 올린 것이라 `running`일 때만 쓸모가 있다. 대기 중인 일감의
 * `stage`는 서버가 줄을 세우며 넣어 둔 말이라, 여기서 다시 적으면 겹친다.
 */
function jobLine(job: PrequizJob, runner: RunnerBeat | null): string {
  const alive = runner?.lastSeen
    ? Date.now() - new Date(runner.lastSeen).getTime() < RUNNER_STALE_MS
    : false;
  if (!alive) {
    // 러너가 없으면 이 일감은 안 움직인다. 만들다 만 것과 아직 시작도 못 한 것을
    // 가른다 — 앞의 것은 다시 붙으면 이어 잡고(`claim`이 running부터 준다),
    // 뒤의 것은 띄우기만 하면 된다.
    return job.state === "running"
      ? `러너가 안 붙어 있습니다 · ${job.stage || "시작"}에서 멈췄습니다`
      : "러너가 안 붙어 있습니다 · 노트북에서 띄우면 집어 갑니다";
  }
  if (job.state === "running") return `${job.force ? "다시 " : ""}만드는 중 · ${job.stage || "시작"}`;
  // 줄은 섰고 러너도 있다. 그런데 한 번에 한 편만 만든다 — 앞 편이 있으면 그것부터다.
  const soon = runner?.busy ? "차례를 기다립니다 · 러너가 앞 편을 만드는 중입니다" : "러너가 곧 집어 갑니다";
  return job.force ? `다시 만듭니다 · ${soon}` : soon;
}

/**
 * 덱 한 줄. 학생에게는 받는 줄이고, **관리자에게는 만드는 자리다.**
 *
 * 덱이 없다는 것을 알아차리는 곳이 여기다 — 캘린더에서 강의를 눌러 「아직
 * 없습니다」를 본 순간. 그때 `/admin` 표까지 걸어가게 하면 대개 안 간다.
 *
 * 만드는 것은 노트북이므로 여기서 하는 일은 일감 한 줄을 적는 것까지다. 한 편에
 * 15분이 걸려서 누른 자리에서 기다릴 수 없고, 그래서 **진행이 이 줄로 돌아온다.**
 *
 * **두 갈래가 같은 부품을 쓴다**(`kind`). 예습과 복습은 재료도 만드는 명령도
 * 다르지만(그 갈래는 러너가 안다), 여기서 사람이 하는 일은 한 가지다 — 없는 것을
 * 보고 누르고, 진행을 같은 자리에서 읽는다. 갈라 두면 한쪽에 붙인 손질이 다른
 * 쪽에 안 붙는다.
 */
export function DeckSlot({
  kind,
  label,
  file,
  lecture,
  onDownload,
  quiet,
}: {
  kind: DeckKind;
  label: string;
  file: LectureFile | undefined;
  lecture: LectureRef;
  onDownload: (file: LectureFile) => void;
  quiet?: boolean;
}) {
  const isAdmin = Boolean(useMe()?.isAdmin);
  if (!isAdmin) {
    return <DeckAction file={file} label={label} onDownload={onDownload} quiet={quiet} />;
  }
  return (
    <DeckMake kind={kind} label={label} file={file} lecture={lecture} onDownload={onDownload} quiet={quiet} />
  );
}

/** 「다시 만들기」를 누르면 무엇이 일어나는지. **갈래마다 재료가 다르다.** */
const REMAKE_MESSAGE: Record<DeckKind, string> = {
  pre: "지금 있는 문항을 버리고, 저장된 예습 링크로 처음부터 다시 만듭니다. 15분쯤 걸리고 다 되면 이 자리의 덱이 새것으로 바뀝니다. 이미 받아 간 사람의 덱은 그대로 남습니다.",
  main: "지금 있는 문항을 버리고, 올해 강의록으로 처음부터 다시 만듭니다. 15분쯤 걸리고 다 되면 이 자리의 덱이 새것으로 바뀝니다. 이미 받아 간 사람의 덱은 그대로 남습니다.",
};

/**
 * 관리자가 보는 덱 줄. 없으면 만들고, 있으면 **다시 만들 수 있다.**
 *
 * 둘을 한 부품으로 두는 이유는 일감이 하나이기 때문이다. 만드는 중이라는 말도,
 * 실패했다는 말도, 덱이 있든 없든 같은 자리에서 같은 모양으로 돌아와야 한다.
 *
 * **일감을 갈래로 물어본다**(`?kind=`). 안 가르면 복습을 만드는 중이라는 말이
 * 예습 자리에도 떠서, 사람이 누르지 않은 것을 기다리게 된다.
 */
function DeckMake({
  kind,
  label,
  file,
  lecture,
  onDownload,
  quiet,
}: {
  kind: DeckKind;
  label: string;
  file: LectureFile | undefined;
  lecture: LectureRef;
  onDownload: (file: LectureFile) => void;
  quiet?: boolean;
}) {
  const base = `/api/admin/lectures/${encodeURIComponent(lecture.subject)}/${encodeURIComponent(lecture.runId)}`;
  const [job, setJob] = useState<PrequizJob | null>(null);
  const [runner, setRunner] = useState<RunnerBeat | null>(null);
  const [asking, setAsking] = useState(false);
  const [askingRemake, setAskingRemake] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(() => {
    api<{ job: PrequizJob | null; runner: RunnerBeat | null }>(`${base}/prequiz-job?kind=${kind}`)
      .then((answer) => {
        setJob(answer.job);
        setRunner(answer.runner);
      })
      .catch(() => {});
  }, [base, kind]);

  useEffect(load, [load]);

  const open = job?.state === "queued" || job?.state === "running";
  useEffect(() => {
    // 도는 동안만 다시 읽는다. 한 편에 15분이라 사람이 패널을 닫았다 열어야
    // 진행이 보이면, 그 진행은 없는 것과 같다.
    if (!open) return;
    const timer = window.setInterval(load, 10_000);
    return () => window.clearInterval(timer);
  }, [open, load]);

  // 끝나면 강의 상세를 다시 읽는다. **덱이 바뀌었는데 이 줄은 옛 크기를 들고
  // 있다** — 다 됐다는 말과 눈앞의 것이 어긋나면 사람은 새로고침을 배워야 한다.
  // 예습 링크가 밖에서 저장될 때 쓰는 신호를 그대로 쓴다(상세를 다시 읽는 일이다).
  const wasOpen = useRef(false);
  useEffect(() => {
    if (wasOpen.current && !open && job?.state === "done") bumpPreviewVersion();
    wasOpen.current = open;
  }, [open, job?.state]);

  async function ask(force: boolean) {
    setAsking(true);
    setError("");
    try {
      const answer = await api<{ job: PrequizJob }>(`${base}/prequiz-job?kind=${kind}`, {
        method: "POST",
        body: force ? JSON.stringify({ force: true }) : undefined,
      });
      setJob(answer.job);
      // 이미 러너가 집어 간 편에는 「다시」가 안 걸린다. 조용히 넘기면 15분을
      // 기다린 끝에 옛 덱이 그대로 있는 것을 보게 된다.
      if (force && !answer.job.force) {
        setError("이미 만드는 중이라 이번 판에는 안 걸립니다. 끝난 뒤에 다시 눌러 주세요.");
      }
    } catch (cause) {
      setError((cause as Error).message);
    } finally {
      setAsking(false);
    }
  }

  const key = quiet ? "" : " is-key";
  // 실패는 남긴다. 조용히 지우면 「눌렀는데 아무 일도 없었다」가 된다.
  const failure = (
    <>
      {job?.state === "failed" ? <p className="notice is-error">{job.message}</p> : null}
      {error ? <p className="notice is-error">{error}</p> : null}
    </>
  );

  if (file) {
    return (
      <>
        <div className="panel-row">
          <DeckAction file={file} label={label} onDownload={onDownload} quiet={quiet} />
          {/* 덱이 이상하다는 것을 아는 사람은 그것을 받아 본 사람이다. 그 사람이
              서 있는 자리가 이 줄이라 여기에 붙인다. 링크 다시 만들기와 같은
              크기·같은 모양이다 — 드물게 하는 일이라는 뜻이 크기에 들어 있다. */}
          <Remake
            label={`${label} 다시 만들기`}
            busy={job?.state === "running"}
            busyLabel="다시 만드는 중…"
            disabled={open || asking}
            onClick={() => setAskingRemake(true)}
          />
        </div>
        {askingRemake ? (
          <RemakeConfirm
            message={REMAKE_MESSAGE[kind]}
            confirm="다시 만들기"
            onConfirm={() => {
              setAskingRemake(false);
              void ask(true);
            }}
            onCancel={() => setAskingRemake(false)}
          />
        ) : null}
        {/* 덱이 있으므로 이 줄은 자리를 뺏지 않고 아래에 붙는다. */}
        {open && job ? <p className="panel-hint">{label} — {jobLine(job, runner)}</p> : null}
        {failure}
      </>
    );
  }

  if (open && job) {
    // `is-empty`는 한 줄짜리 자리다(`display: block`). 옆의 「아직 없습니다」와
    // 같은 꼴로 적는다 — strong·small을 넣으면 저 혼자 두 줄로 서서 눈에 걸린다.
    return <span className={`panel-action${key} is-empty`}>{label} — {jobLine(job, runner)}</span>;
  }

  return (
    <>
      <button className={`panel-action${key}`} disabled={asking} onClick={() => void ask(false)}>
        <strong>{label} 만들기</strong>
        <small>{asking ? "맡기는 중…" : "아직 없습니다 · 눌러서 만듭니다"}</small>
      </button>
      {failure}
    </>
  );
}

function DeckAction({
  file,
  label,
  onDownload,
  quiet = false,
}: {
  file: LectureFile | undefined;
  label: string;
  onDownload: (file: LectureFile) => void;
  /** 위에 그 덱의 웹 풀이가 서 있는가. 그러면 이 줄은 한 단 낮게 눕는다. */
  quiet?: boolean;
}) {
  const key = quiet ? "" : " is-key";
  // 아직 없는 것도 자리를 남긴다. 목록에서 빠지면 "없다"와 "이 강의에는 원래
  // 해당 없다"를 구분할 수 없다.
  if (!file) return <span className={`panel-action${key} is-empty`}>{label} — 아직 없습니다</span>;
  return (
    <button className={`panel-action${key} is-download`} onClick={() => onDownload(file)}>
      <strong>{label}</strong>
      <small>{fileSize(file.sizeBytes)} · 내려받기</small>
    </button>
  );
}
