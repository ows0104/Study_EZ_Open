/** 러너가 아직 안 집었거나(`queued`), 만드는 중이거나(`running`), 끝났거나. */
/**
 * `held`는 **자동으로 섰지만 그날 상한을 넘어 사람을 기다리는 줄**이다(2026-09-01).
 * 만들지는 않지만 화면에는 남는다 — 안 세우면 「자동이 안 걸린 편」과 「상한에
 * 걸린 편」이 같은 모양이 된다.
 */
/**
 * `canceled`는 **사람이 지우거나 멈춘 줄**이다(2026-09-03). 실패와 갈라 둔다 —
 * 실패는 고칠 것이 있다는 뜻이고 이것은 사람이 안 만들기로 한 것이다.
 */
export type PrequizJobState = "queued" | "running" | "done" | "failed" | "held" | "canceled";

/** 누가 세운 줄인가. 버튼은 이제 안전장치고, 재료가 도착하면 저절로 선다. */
export type JobOrigin = "button" | "auto";

/** 무엇을 만드는 일감인가. 재료도 명령도 갈린다 — 예습은 예습 대화와 작년 필기로,
 *  복습은 올해 필기로 만든다. */
export type DeckKind = "pre" | "main" | "bank";
export type JobKind = DeckKind | "points";

/**
 * 「덱 만들기」를 누른 것. 만드는 곳은 노트북이라 여기서는 상태만 본다.
 *
 * `stage`는 러너가 하위 프로세스의 `── ` 줄을 그대로 올려 준 것이다. 한 편에
 * 15분이 걸려서, 「도는 중」만으로는 멈춘 것과 구별이 안 된다.
 */
/**
 * `GET /api/lectures/{subject}/{runId}/deck-job` — **학생이 보는 진행.**
 *
 * 2026-09-21 관리자 지시로 생겼다. `PrequizJob`에서 운영의 칸을 덜어 낸 것이고
 * (누가 눌렀나 · 어느 일꾼이 잡았나 · 왜 실패했나 · 줄 순서), **서버가 덜어서
 * 준다**(`routes/prequiz_jobs.watch_row`). 화면에서 가리는 것이 아니다 —
 * 가리기만 하면 남의 이메일이 응답에는 그대로 실려 온다.
 *
 * 열린 일감만 온다. `done`이면 덱이 그 자리에 있고, `failed`·`canceled`는
 * 학생이 할 일이 없어 「아직 없습니다」가 그대로 참이다.
 *
 * **`PrequizJob`이 이것을 통째로 품고 있다.** 그래서 `progressLine`·`stageLabel`
 * 같은 셈은 이 좁은 쪽을 받고, 관리자의 일감도 그대로 넣을 수 있다.
 */
export type DeckWatch = {
  kind: JobKind;
  state: PrequizJobState;
  /** 러너가 올린 진행(`② 카드`). **`running`이 아니면 빈 문자열이다** — 줄 서 있는
   *  일감의 `stage`는 서버가 넣어 둔 안내문이라 단계 이름이 아니다. */
  stage: string;
  stageIndex: number;
  stageTotal: number;
  elapsedSeconds: number;
  stageSeconds: number;
  /** 0이면 아직 모른다는 뜻이고, 그때 화면은 그 자리를 비운다. */
  etaSeconds: number;
  /** 이미 있는 덱을 버리고 다시 만드는 중인가. 받아 간 덱이 곧 바뀐다는 뜻이다. */
  force: boolean;
  /** 모델 한도로 멈춘 편이 언제 저절로 이어지는가(ISO 시각). */
  resumeAt: string;
};

/** `deck-job`이 같이 주는 러너. **살아 있는지만 말한다** — `busy`·`note`는
 *  다른 편의 이름이라 이 편을 보러 온 사람에게 갈 자리가 아니다. */
export type DeckWatchRunner = { lastSeen: string };

export type PrequizJob = {
  id: number;
  subject: string;
  runId: string;
  kind: JobKind;
  state: PrequizJobState;
  stage: string;
  message: string;
  requestedBy: string;
  /** 「다시 만들기」로 선 일감인가. 러너가 이미 만든 것을 버리고 처음부터 만든다. */
  force: boolean;
  origin: JobOrigin;
  /** 어느 일꾼이 잡고 있나(`w1`·`w2`). 겹쳐 도는 편을 가려 보는 값이다. */
  worker: string;
  /**
   * 모델 한도로 멈춘 편이 **언제 저절로 이어지는가**(ISO 시각). 빈 문자열이면
   * 그냥 차례를 기다리는 줄이다.
   *
   * 이 값이 없으면 화면이 「기다리는 중」밖에 못 말하고, 그러면 사람이 다시
   * 눌러야 하는 줄로 읽는다 — 누를 필요가 없는데.
   */
  resumeAt: string;
  /**
   * 왜 이 줄이 거기 섰나 — `내일 예습` · `오늘 복습`, 아니면 빈 문자열.
   *
   * **화면이 다시 세지 않는다.** 하루가 바뀌는 시각을 서버가 새벽 5시로 잡고
   * 있어서(`QUEUE_DAY_START_HOUR`), 여기서 자정으로 세면 새벽에 두 자리가
   * 다른 말을 한다.
   */
  priority: string;
  /** 사람이 옮긴 자리. 0이 아니면 자동 순위를 덮고 있다. */
  queueRank: number;
  /**
   * 사람이 「멈추기」를 눌렀고 러너가 아직 안 받아 갔다.
   *
   * **서버는 노트북의 프로세스를 모른다.** 그래서 도는 편은 이 표시가 켜진 채로
   * 잠시 `running`에 남아 있고, 러너가 진행을 적으러 올 때 받아 가 자식을 죽인다.
   * 화면은 그동안 「멈추는 중」이라고 말해야 한다 — 「만드는 중」으로 두면 누른
   * 사람이 안 눌린 줄 알고 다시 누른다.
   */
  cancelRequested: boolean;
  /**
   * 러너가 만들기 전에 사람에게 묻는 말. **비어 있지 않으면 이 줄은 `held`로 서서
   * 전략을 고르기를 기다린다**(2026-09-24 관리자 지시 — 표시해 둔 편은 돌릴 때
   * 알림을 띄워 고르게). 고르는 자리는 `POST /api/admin/prequiz-jobs/{id}/choose`.
   */
  ask: string;
  /** 사람이 고른 전략(`기본`·`족보`·`필기`·`사진`). 빈 문자열이면 자동 판정이다. */
  strategy: string;
  /** **서버가 셈해서 준다.** 화면마다 시계를 맞추면 시차만큼 어긋난다. */
  elapsedSeconds: number;
  stageSeconds: number;
  stageIndex: number;
  stageTotal: number;
  /**
   * 러너가 지난 편들의 실측으로 셈한 남은 시간. **0이면 모른다는 뜻**이고,
   * 그때 화면은 그 자리를 비운다 — 지어낸 숫자를 적으면 그 뒤로 아무도 그
   * 값을 안 믿는다.
   *
   * 러너가 20초마다 다시 셈해 올리므로 **그대로 쓰면 된다** — 마지막으로 적힌
   * 순간 기준의 남은 시간이다.
   */
  etaSeconds: number;
  createdAt: string;
  updatedAt: string;
};

/** 노트북이 마지막으로 살아 있다고 알린 시각. 없으면 한 번도 안 붙은 것이다. */
export type RunnerBeat = { lastSeen: string; busy: boolean; note: string };

/**
 * `GET /api/admin/prequiz-jobs` — **겹쳐 도는 편을 순서대로 보는 자리.**
 *
 * `/overview`는 편마다 최근 일감을 하나씩만 들고 있어서 「지금 둘이 도는데 앞에
 * 몇 편이 남았나」를 말할 수 없다. 도는 것·기다리는 것·상한에 걸린 것을 서버가
 * 갈라서 준다 — 화면마다 갈라 보면 답이 화면마다 달라진다.
 */
export type JobBoard = {
  jobs: PrequizJob[];
  running: PrequizJob[];
  /** 집어 갈 차례대로. 앞에서부터 러너가 가져간다. */
  waiting: PrequizJob[];
  held: PrequizJob[];
  autoUsedToday: number;
  autoDailyCap: number;
  maxRunning: number;
  runner: RunnerBeat | null;
};
