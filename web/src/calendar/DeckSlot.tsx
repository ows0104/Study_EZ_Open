import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { api } from "../api";
import { bumpPreviewVersion } from "../bridge/previewBridge";
import { type DeckKind, type DeckWatch, type DeckWatchRunner, type PrequizJob, type RunnerBeat } from "../types/jobs";
import { type LectureFile, type LectureRef } from "../types/lectures";
import { jobMoving, progressLine, runnerAlive, waitingUntil, watchLine } from "../jobProgress";
import { useMe } from "../useMe";
import { ActionCard, fileSize, Remake, RemakeConfirm } from "./panelShared";

/**
 * 덱 한 칸. 만들어졌으면 내려받고, 아니면 러너에게 일감을 건다.
 *
 * 일감의 진행은 서버가 알려 준다(`prequiz_jobs.py`). **보는 사람에 따라 경로가
 * 다르다** — 관리자는 `/api/admin/…/prequiz-job`, 학생은 `/api/lectures/…/deck-job`.
 * 뒤의 것은 주는 칸을 덜어 낸 것이라 남의 이메일도 실패 사유도 안 싣는다.
 *
 * `EventPanel` 에서 갈라 나왔다.
 */
/**
 * 좁은 칸에 들어가는 한 마디. **긴 줄은 안 줄이고 아래에 그대로 둔다** — 여기서
 * 자르면 「러너가 안 붙어 있습니다」가 「만드는 중」으로 바뀐다. 그 거짓말을
 * 막으려고 아래 `jobLine`을 갈랐던 것이라 같은 함정을 여기서 다시 판다.
 */
function jobShort(job: PrequizJob, runner: RunnerBeat | null): string {
  if (job.state === "held") return job.ask ? "전략 선택" : "상한";
  if (!runnerAlive(runner)) return "멈춤";
  // 한도로 기다리는 줄은 「대기」와 다르다 — 저쪽은 곧 집어 가고 이쪽은 시각을 기다린다.
  if (waitingUntil(job)) return "한도 대기";
  if (job.cancelRequested) return "멈추는 중";
  return job.state === "running" ? "만드는 중" : "대기";
}

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
  const alive = runnerAlive(runner);
  if (job.state === "held" && job.ask) {
    // 러너가 묻고 있다. 여기서 「지금 만들기」를 눌러도 서버가 거절한다(409) —
    // 답 없이 풀면 러너가 집자마자 또 묻기 때문이다. 고르는 자리를 말해 준다.
    return `${job.ask} — 관리 화면 퀴즈 탭에서 전략을 고르세요`;
  }
  if (job.state === "held") {
    // 재료는 도착했는데 그날 자동 상한을 넘겼다. **누르면 그 줄이 그대로 풀린다** —
    // 새 줄이 서는 것이 아니라 이미 선 줄이 큐로 들어간다.
    return job.stage || "오늘 자동으로 만들 만큼 만들었습니다 — 누르면 이 편을 만듭니다";
  }
  if (!alive) {
    // 러너가 없으면 이 일감은 안 움직인다. 만들다 만 것과 아직 시작도 못 한 것을
    // 가른다 — 앞의 것은 다시 붙으면 이어 잡고(`claim`이 running부터 준다),
    // 뒤의 것은 띄우기만 하면 된다.
    return job.state === "running"
      ? `러너가 안 붙어 있습니다 · ${job.stage || "시작"}에서 멈췄습니다`
      : "러너가 안 붙어 있습니다 · 노트북에서 띄우면 집어 갑니다";
  }
  if (job.state === "running") {
    // 사람이 멈추라고 눌렀는데 러너가 아직 안 받아 갔다. **「만드는 중」이라고
    // 하면 안 된다** — 누른 사람이 안 눌린 줄 알고 다른 자리를 찾으러 간다.
    if (job.cancelRequested) return `멈추는 중 · ${progressLine(job, false)}`;
    // 단계·경과·남은 시간까지 한 줄에(`progressLine`). 그 전에는 「만드는 중」뿐이라
    // 5분째와 40분째가 같은 모양이었다.
    return `${job.force ? "다시 " : ""}만드는 중 · ${progressLine(job)}`;
  }
  // 모델 한도로 멈춘 편. **누를 필요가 없다는 것을 말해야 한다** — 안 그러면
  // 「기다리는 중」으로 보이고, 기다려도 안 되는 줄로 읽혀 사람이 다시 누른다.
  const until = waitingUntil(job);
  if (until) return `세션 한도 — ${until}에 저절로 이어 갑니다`;
  // 줄은 섰고 러너도 있다. 겹쳐 도는 편에 상한이 있어서 앞 편이 차면 기다린다.
  const soon = runner?.busy ? "차례를 기다립니다 · 러너가 다른 편을 만드는 중입니다" : "러너가 곧 집어 갑니다";
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
 *
 * **`before`가 있으면 그것과 한 덩어리로 붙는다.** Pre-Quiz가 그렇다 — 웹에서
 * 푸는 것과 덱으로 받는 것은 한 가지를 하는 두 길인데, 두 줄로 세워 두니 서로
 * 다른 것으로 읽혔다(2026-08-31 관리자 지시 — 하나로 합쳐라).
 *
 * **`before`는 노드가 아니라 「도구를 받아 그리는 것」이다.** 덱 칸은 좁아서
 * 「다시 만들기」가 안 들어가고, 관리자 지시도 그것을 앞칸(웹에서 풀기) 아래에
 * 두라는 것이었다. 도구는 여기서만 만들 수 있으니(일감 상태를 든다) 넘겨준다.
 */
/**
 * 재료가 없어 지금은 못 만드는 사정. **서버의 `_no_material`과 같은 규칙이다** —
 * 거기서 400으로 거절하는 것을 여기서는 눌리지 않게 한다.
 */
export type DeckBlocked = {
  /** 좁은 칸에 드는 말. 「아직 없습니다」가 서던 자리다. */
  short: string;
  /** 무엇을 먼저 해야 하는지. 서버가 거절할 때 하는 말을 그대로 쓴다. */
  why: string;
};

export function DeckSlot({
  kind,
  label,
  file,
  lecture,
  onDownload,
  before,
  blocked,
}: {
  kind: DeckKind;
  label: string;
  file: LectureFile | undefined;
  lecture: LectureRef;
  onDownload: (file: LectureFile) => void;
  /** 같은 덩어리 안에서 이 덱보다 앞에 서는 것(Pre-Quiz 웹 풀이). */
  before?: (tools: ReactNode) => ReactNode;
  /** 재료가 없어 못 만드는가. **관리자에게만 뜻이 있다** — 학생은 받기만 한다. */
  blocked?: DeckBlocked;
}) {
  const isAdmin = Boolean(useMe()?.isAdmin);
  if (!isAdmin) {
    return <DeckWatchSlot label={label} file={file} lecture={lecture} kind={kind} onDownload={onDownload} before={before} />;
  }
  return (
    <DeckMake
      kind={kind}
      label={label}
      file={file}
      lecture={lecture}
      onDownload={onDownload}
      before={before}
      blocked={blocked}
    />
  );
}

/**
 * 학생이 보는 덱 줄. **받는 것은 그대로고, 만들어지는 중이면 그 사실이 붙는다.**
 *
 * 2026-09-21 관리자 지시 — 「퀴즈를 만들고 있을 때 관리자가 아닌 사용자도
 * 사이드패널 현황을 볼 수 있게. 몇 단계 몇 분 남았는지.」
 *
 * 그 전까지 이 자리는 파일 하나만 보고 그렸다. 그래서 **15분 뒤에 오면 되는
 * 편과 아무도 안 만들고 있는 편이 똑같이 「아직 없습니다」였다** — 관리자
 * 화면에는 단계도 남은 시간도 이미 떠 있는데.
 *
 * **누를 자리는 안 준다.** 만드는 것은 관리자의 일이고(`DeckMake`), 여기 있는
 * 것은 읽을 줄 하나다. 그래서 실패도 안 적는다 — 학생이 할 수 있는 일이 없고,
 * 빨간 줄만 남으면 고장으로 읽힌다.
 *
 * 부르는 곳은 학생에게 열린 경로다(`GET /api/lectures/…/deck-job`). 관리자
 * 경로를 열어 준 것이 아니라 **주는 칸을 덜어 낸 경로를 따로 세웠다** — 저쪽은
 * 누가 눌렀는지(남의 이메일)까지 싣는다.
 */
function DeckWatchSlot({
  kind,
  label,
  file,
  lecture,
  onDownload,
  before,
}: {
  kind: DeckKind;
  label: string;
  file: LectureFile | undefined;
  lecture: LectureRef;
  onDownload: (file: LectureFile) => void;
  before?: (tools: ReactNode) => ReactNode;
}) {
  const [job, setJob] = useState<DeckWatch | null>(null);
  const [runner, setRunner] = useState<DeckWatchRunner | null>(null);
  const merged = Boolean(before);

  const load = useCallback(() => {
    const base = `/api/lectures/${encodeURIComponent(lecture.subject)}/${encodeURIComponent(lecture.runId)}`;
    api<{ job: DeckWatch | null; runner: DeckWatchRunner | null }>(`${base}/deck-job?kind=${kind}`)
      .then((answer) => {
        setJob(answer.job);
        setRunner(answer.runner);
      })
      // **조용히 접는다.** 이 줄은 덤이라, 못 읽었다고 받는 자리까지 시끄러워질
      // 이유가 없다. 관리자 쪽과 같은 규칙이다.
      .catch(() => {});
  }, [lecture.subject, lecture.runId, kind]);

  useEffect(load, [load]);

  const moving = jobMoving(job);
  useEffect(() => {
    // 도는 동안만 다시 읽는다(관리자 쪽과 같은 10초). 한 편에 15분이라 패널을
    // 닫았다 열어야 진행이 바뀌면, 그 진행은 없는 것과 같다.
    if (!moving) return;
    const timer = window.setInterval(load, 10_000);
    return () => window.clearInterval(timer);
  }, [moving, load]);

  // 다 되면 강의 상세를 다시 읽는다 — **덱이 도착했는데 이 줄은 「아직
  // 없습니다」를 들고 있다.** 기다린 사람에게 새로고침을 가르칠 자리가 아니다.
  const wasMoving = useRef(false);
  useEffect(() => {
    if (wasMoving.current && !moving) bumpPreviewVersion();
    wasMoving.current = moving;
  }, [moving]);

  const line = job ? watchLine(job, runner) : "";
  return (
    <>
      <Combo before={before?.(null)}>
        {/* 덱이 없고 만드는 중이면 「아직 없습니다」 자리를 그 말이 받는다.
            좁은 칸(`merged`)에는 한 마디만 들고, 사정은 아래 줄이 통째로 말한다. */}
        {job && !file && line ? (
          <span className={`panel-action is-line is-empty${merged ? " is-compact" : " is-key"}`}>
            {merged ? watchShort(job, runner) : `${label} — ${line}`}
          </span>
        ) : (
          <DeckAction file={file} label={label} onDownload={onDownload} merged={merged} />
        )}
      </Combo>
      {/* 덱이 있는데 다시 만드는 중이면 아래에 붙는다 — 지금 받는 것이 옛것이라는
          뜻이라, 받는 칸을 가리지 않고 사실만 더한다. */}
      {line && (file || merged) ? <p className="panel-hint">{label} — {line}</p> : null}
    </>
  );
}

/**
 * 좁은 칸에 드는 한 마디. **긴 줄은 안 줄이고 아래에 그대로 둔다.**
 *
 * `watchLine` 이 빈 문자열을 돌려준 줄에는 안 불린다 — 부르는 쪽이 그 줄을 아예
 * 안 그린다. 그래서 여기에 「기다려도 안 오는 줄」(`held`)의 갈래가 없다.
 */
function watchShort(job: DeckWatch, runner: DeckWatchRunner | null): string {
  if (job.state === "running") return runnerAlive(runner) ? "만드는 중" : "멈춤";
  return waitingUntil(job) ? "이어서 만듭니다" : "곧 만듭니다";
}

/**
 * 덱 하나를 담는 자리. `before`가 있으면 테두리 하나 안에 둘을 넣고 가운데를
 * 선으로 가른다 — 두 길이지 두 가지가 아니라는 뜻이다.
 */
function Combo({ before, children }: { before?: ReactNode; children: ReactNode }) {
  if (!before) return <>{children}</>;
  return (
    <div className="panel-combo">
      {before}
      {children}
    </div>
  );
}

/** 「다시 만들기」를 누르면 무엇이 일어나는지. **갈래마다 재료가 다르다.** */
const REMAKE_MESSAGE: Record<DeckKind, string> = {
  pre: "지금 있는 문항을 버리고, 저장된 예습 링크로 처음부터 다시 만듭니다. 15분쯤 걸리고 다 되면 이 자리의 덱이 새것으로 바뀝니다. 이미 받아 간 사람의 덱은 그대로 남습니다.",
  main: "지금 있는 문항을 버리고, 올해 강의록으로 처음부터 다시 만듭니다. 15분쯤 걸리고 다 되면 이 자리의 덱이 새것으로 바뀝니다. 이미 받아 간 사람의 덱은 그대로 남습니다.",
  // Quiz Bank 는 이 부품을 안 쓴다(`bank/BankPanel.tsx`). 갈래 이름이 같은 표를 쓰므로 칸만 채운다.
  bank: "저장된 ChatGPT 응답을 다시 정리하고 검토합니다. 몇 분 걸립니다.",
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
  before,
  blocked,
}: {
  kind: DeckKind;
  label: string;
  file: LectureFile | undefined;
  lecture: LectureRef;
  onDownload: (file: LectureFile) => void;
  before?: (tools: ReactNode) => ReactNode;
  blocked?: DeckBlocked;
}) {
  const base = `/api/admin/lectures/${encodeURIComponent(lecture.subject)}/${encodeURIComponent(lecture.runId)}`;
  const [job, setJob] = useState<PrequizJob | null>(null);
  const [runner, setRunner] = useState<RunnerBeat | null>(null);
  const [asking, setAsking] = useState(false);
  const [askingRemake, setAskingRemake] = useState(false);
  const [error, setError] = useState("");
  const merged = Boolean(before);

  const load = useCallback(() => {
    api<{ job: PrequizJob | null; runner: RunnerBeat | null }>(`${base}/prequiz-job?kind=${kind}`)
      .then((answer) => {
        setJob(answer.job);
        setRunner(answer.runner);
      })
      .catch(() => {});
  }, [base, kind]);

  useEffect(load, [load]);

  // `held`는 사람을 기다리는 줄이라 안 움직인다 — 다시 읽어 봐야 같은 값이다.
  const open = jobMoving(job);
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

  /* 실패는 남긴다. 조용히 지우면 「눌렀는데 아무 일도 없었다」가 된다.
   *
   * **다만 그 말이 아직 참일 때까지다(2026-08-31 관리자 지시 — 덱이 생겼는데
   * 로그가 남아 있다).** 덱을 만드는 길은 이 버튼 하나가 아니다 — 야간 쓸기도
   * 올린다. 「만들기」가 실패했다는 말은 그렇게 덱이 도착한 순간 거짓이 된다.
   *
   * 「다시 만들기」는 다르다. 그 말은 **눈앞의 덱이 옛것**이라는 뜻이라, 덱이
   * 있어도 그대로 참이다. 그래서 `force`가 아닌 실패만 접는다. */
  const moot = Boolean(file) && !job?.force;
  const failure = (
    <>
      {job?.state === "failed" && !moot ? <p className="notice is-error">{job.message}</p> : null}
      {error ? <p className="notice is-error">{error}</p> : null}
    </>
  );

  if (file) {
    /* 덱이 이상하다는 것을 아는 사람은 그것을 받아 본 사람이다. 그 사람이 서
       있는 자리가 이 덩어리라 **버튼도 그 안에 넣는다**(2026-08-31 관리자 지시).
       덩어리가 둘로 갈려 있으면 넓은 앞칸이 든다 — 덱 칸은 이름과 용량으로
       이미 한 줄이 찬다. */
    const tools = (
      <Remake
        label="다시 만들기"
        hint={blocked ? blocked.why : `${label} 다시 만들기`}
        busy={job?.state === "running"}
        busyLabel="다시 만드는 중…"
        disabled={open || asking || Boolean(blocked)}
        onClick={() => setAskingRemake(true)}
      />
    );
    return (
      <>
        <Combo before={before?.(tools)}>
          <DeckAction
            file={file}
            label={label}
            onDownload={onDownload}
            merged={merged}
            tools={merged ? undefined : tools}
          />
        </Combo>
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
    // `is-line`은 한 줄짜리 자리다. 옆의 「아직 없습니다」와 같은 꼴로 적는다 —
    // strong·small을 넣으면 저 혼자 두 줄로 서서 눈에 걸린다.
    //
    // 좁은 칸(`merged`)에는 한 마디만 들어간다. 사정은 아래 줄이 통째로 말한다.
    return (
      <>
        <Combo before={before?.(null)}>
          <span className={`panel-action is-line is-empty${merged ? " is-compact" : " is-key"}`}>
            {merged ? jobShort(job, runner) : `${label} — ${jobLine(job, runner)}`}
          </span>
        </Combo>
        {merged ? <p className="panel-hint">{label} — {jobLine(job, runner)}</p> : null}
        {failure}
      </>
    );
  }

  /* 재료가 없으면 누를 자리를 안 준다(2026-08-31 관리자 지시 — 올해 필기가 안
     들어왔는데 버튼이 켜져 있다). 서버는 이미 400으로 거절하고 있었는데
     (`_no_material`), 그 말은 **누른 뒤에야** 보였다. 여기서 같은 규칙을 눈으로
     먼저 말한다 — 「아직 없습니다」와 같은 꼴이라 무엇을 기다리는지만 다르다. */
  if (blocked) {
    return (
      <>
        <Combo before={before?.(null)}>
          <ActionCard
            shape={`is-empty ${merged ? "is-compact" : "is-key"}`}
            hit={
              <span className="panel-action-hit" title={blocked.why}>
                <strong>{label}</strong>
                <small>{blocked.short}</small>
              </span>
            }
          />
        </Combo>
        {failure}
      </>
    );
  }

  return (
    <>
      <Combo before={before?.(null)}>
        <ActionCard
          shape={merged ? "is-compact" : "is-key"}
          hit={
            <button className="panel-action-hit" disabled={asking} onClick={() => void ask(false)}>
              <strong>{label}</strong>
              <small>{asking ? "맡기는 중…" : job?.state === "held" ? "지금 만들기" : "만들기"}</small>
            </button>
          }
        />
      </Combo>
      {/* 자동으로 서 있다가 그날 상한에 걸린 줄. **왜 아직 없는지를 여기서
          말한다** — 안 적으면 자동이 안 걸린 편과 같은 모양이 된다. */}
      {job?.state === "held" ? <p className="panel-hint">{label} — {jobLine(job, runner)}</p> : null}
      {failure}
    </>
  );
}

function DeckAction({
  file,
  label,
  onDownload,
  merged = false,
  tools,
}: {
  file: LectureFile | undefined;
  label: string;
  onDownload: (file: LectureFile) => void;
  /** 앞의 것과 한 테두리 안에 들어가는가. 그러면 좁은 칸으로 눕는다. */
  merged?: boolean;
  /** 카드 안에 드는 작은 버튼(관리자의 「다시 만들기」). */
  tools?: ReactNode;
}) {
  const shape = merged ? "is-compact" : "is-key";
  // 아직 없는 것도 자리를 남긴다. 목록에서 빠지면 "없다"와 "이 강의에는 원래
  // 해당 없다"를 구분할 수 없다.
  if (!file) {
    return (
      <ActionCard
        shape={`is-empty ${shape}`}
        hit={
          <span className="panel-action-hit">
            <strong>{label}</strong>
            <small>{merged ? "없습니다" : "아직 없습니다"}</small>
          </span>
        }
      />
    );
  }
  return (
    <ActionCard
      shape={`is-download ${shape}`}
      hit={
        <button className="panel-action-hit" onClick={() => onDownload(file)}>
          <strong>{label}</strong>
          <small>{fileSize(file.sizeBytes)}</small>
        </button>
      }
      tools={tools}
    />
  );
}
