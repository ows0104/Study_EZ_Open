/** 로그인 직후 무엇을 그릴지 정하는 값. 승인 게이트를 지나지 않는 응답이다. */
export type Me = {
  id: string;
  email: string;
  isAdmin: boolean;
  isApproved: boolean;
};

/** 예습 대화를 열 수 있는 AI 서비스. 확장과 서버가 같은 세 값을 쓴다. */
export type PreviewProvider = "chatgpt" | "gemini" | "claude";

export const previewProviders: PreviewProvider[] = ["chatgpt", "gemini", "claude"];

export const previewProviderLabels: Record<PreviewProvider, string> = {
  chatgpt: "ChatGPT",
  gemini: "Gemini",
  claude: "Claude",
};

export type AppUser = {
  id: string;
  email: string;
  isAdmin: boolean;
  isApproved: boolean;
  createdAt: string | null;
};

/**
 * 사람 하나의 이용현황. **서버가 세는 것은 웹에서 한 것과 받아 간 것뿐이다.**
 *
 * apkg로 나간 풀이는 안키가 들고 서버에 안 남는다. 그래서 이 수들을 더해
 * "얼마나 공부했나"로 그리면 안 된다 — 사연은 `server/app/routes/usage.py` 머리에 있다.
 *
 * **`cards`·`decks`·`opens`는 고른 기간 안의 값이다.** `lastAt`만 기간을 안 탄다.
 */
export type UsageRow = {
  id: string;
  email: string;
  isAdmin: boolean;
  /** Study_EZ에 들어갈 수 있는가. **0이 「안 썼다」인지 「못 썼다」인지를 가른다.** */
  hasAccess: boolean;
  joinedAt: string | null;
  /** 마지막으로 무엇이든 한 때. `null`이면 한 번도 안 열었다. **기간을 안 탄다.** */
  lastAt: string | null;
  /** 이 기간에 웹에서 푼 카드 수. 한 줄이 한 장이라 같은 카드를 여러 번 봐도 한 장이다. */
  cards: number;
  /** 이 기간에 파일을 받아 간 편 수. **받아 간 것이지 푼 것이 아니다.** */
  decks: number;
  /**
   * 이 기간에 예습 링크를 연 편 수. `share`가 기본 링크, `mine`이 개인 대화다.
   *
   * **우리 화면에서 누른 것만 든다** — 링크를 복사해 받은 사람이 연 것은 그 주소가
   * 서버를 안 지나므로 안 들어온다.
   */
  opens: { share: number; mine: number };
  /** 저장해 둔 개인 예습 대화 수. 기간을 안 탄다 — 펴서 보는 자리에 쓴다. */
  previews: number;
  /** 예습 프롬프트를 고쳐 썼는가. 비어 있으면 화면의 기본 문구를 쓴다. */
  prompt: { custom: boolean; chars: number };
};

/** 무엇을 잰 기간인가. `to`가 `null`이면 지금까지다. */
export type UsageWindow = {
  key: string;
  /** 「이번 블럭 · 미생물학」처럼 **무엇인지**를 적어서 온다. */
  label: string;
  from: string | null;
  to: string | null;
};

export type UsageBoard = {
  now: string;
  /**
   * **고른 것이 아니라 실제로 잰 기간이다.** 블럭이 아직 없으면 서버가 최근 7일로
   * 내려앉히고 그 사실이 여기 온다.
   */
  window: UsageWindow;
  /** 고를 수 있는 기간들. 순서가 화면의 버튼 순서다. */
  windows: { key: string; label: string }[];
  /**
   * 예습 링크 열기가 **언제부터 남았는가**. 표가 선 날이다.
   *
   * 이 값이 있어야 화면이 0을 「안 했다」와 「기록이 없다」로 가를 수 있다.
   */
  opensSince: string | null;
  users: UsageRow[];
};

/** 한 사람이 강의 하나에서 한 것. `title`이 비면 지워진 편이다. */
export type UsageLecture = {
  subject: string;
  runId: string;
  title: string;
  date: string | null;
  /** `selfCorrect`는 **본인이 맞다고 찍은 것**이다. 서버 판정이 아니다. */
  pre: { cards: number; selfCorrect: number; grades: number };
  main: { cards: number; selfCorrect: number; grades: number };
  grabs: string[];
  /** 이 편의 개인 대화를 저장해 뒀는가. */
  preview: boolean;
  /** 이 편의 예습 링크를 우리 화면에서 누른 **횟수**. 요약과 달리 편이 아니다. */
  opens: { share: number; mine: number };
  lastAt: string | null;
};

export type UsageDetail = {
  /** `previewPrompt`는 고쳐 쓴 사람만 값이 있다. 빈 문자열이 곧 「기본 문구」다. */
  user: { id: string; email: string; previewPrompt: string };
  now: string;
  lectures: UsageLecture[];
};

export type EventCategory = "lecture" | "practice" | "exam" | "holiday" | "elective" | "study";

/**
 * 강의에 무엇이 올라와 있는가. 있다/없다만 안다.
 *
 * **다섯 칸이 관리자 체크리스트와 하나씩 짝이다.** 앞 셋이 예습 자리로, 뒤 둘이
 * 복습 자리로 묶여 칸의 점 둘이 된다.
 *
 * `quiz`는 본덱(`main_apkg`)만이다. 예습덱은 `prequiz`가 따로 든다 — 둘은
 * 쓰는 시점이 달라서 같은 점으로 그리면 어느 쪽도 안 뜻한다.
 */
export type Marks = {
  /** 작년 필기. 예습으로 읽는 것이라 올해 것과 다른 자리에 선다. */
  notesPrev: boolean;
  preview: boolean;
  prequiz: boolean;
  notesCurrent: boolean;
  quiz: boolean;
};

/**
 * 이 사람이 받아 갔는가. 자리 둘로 묶여 온다.
 *
 * **덱에서 "했다"를 아는 유일한 길이다.** apkg는 Anki에서 풀리므로 풀이 기록이
 * 서버에 없지만, 파일이 나가려면 서명을 받아 가야 하고 그 서명은 사용자가
 * 버튼을 눌러야 나간다. 그래서 이것은 *받아 갔다*지 *풀었다*가 아니다.
 */
export type Grabbed = {
  pre: boolean;
  main: boolean;
};

/**
 * 웹 예습퀴즈를 몇 개까지 풀었는가.
 *
 * **이 사람의 값이다.** 그리고 잴 수 있는 유일한 "했다"이기도 하다 — 덱은
 * apkg로 나가 Anki에서 풀리므로 서버에 기록이 없다.
 */
export type PrequizProgress = {
  total: number;
  answered: number;
};

export type LectureRef = {
  subject: string;
  runId: string;
  title: string;
  professors: string[];
  marks: Marks;
  /** 웹에서 풀 문항이 없으면 없다. "안 풀었다"와 "잴 것이 없다"는 다르다. */
  prequizProgress: PrequizProgress | null;
  grabbed: Grabbed;
};

export type TimetableEvent = {
  id: string;
  date: string;
  startTime: string;
  endTime: string;
  title: string;
  details: string;
  professor: string;
  category: EventCategory;
  course: string;
  slot: number | null;
  /** 한 칸에 여러 강의가 붙을 수 있다. 선택형 과목이 그렇다. */
  lectures: LectureRef[];
};

export type LectureFile = {
  id: string;
  kind: "notes_prev" | "notes_current" | "pre_apkg" | "main_apkg";
  label: string;
  filename: string;
  sizeBytes: number;
};

export type MissedItem = {
  itemId: string;
  stem: string;
  answer: string;
  /** 왜 이것이 「꼭 반드시」인가 — spine·vocabulary·mechanism·clinical·repeated. */
  focus: string;
  cardType: string;
  explanation: string;
  slideNo: number | null;
  examHit: boolean;
};

/** 웹 풀이의 갈래. 서버 경로도 이 이름을 그대로 쓴다(`prequiz` / `mainquiz`). */
export type QuizKind = "pre" | "main";

export interface QuizProgress {
  itemCount: number;
  /**
   * 이 편을 한 번이라도 훑은 장수. **오늘 낼 카드 수와 다른 것을 말한다** —
   * 다 훑은 편에도 오늘 낼 카드가 있고, 오늘 낼 것이 없는 편도 안 끝난 것이다.
   * 그래서 서버가 둘을 더하지 않고 나란히 보낸다.
   */
  answered: number;
  correct: number;
  missed: MissedItem[];
  /** 한 번도 안 찍은 카드. */
  new: number;
  /** 익히는 중이고 지금 낼 것. */
  learning: number;
  /** 익었고 지금 낼 것. */
  review: number;
  /** 아직 때가 아닌 것. */
  later: number;
  /** 지금 낼 것 전부 — 위 셋의 합이다. */
  due: number;
  /** 아직 때가 아닌 것 중 가장 이른 때. 없으면 `null`. */
  nextDueAt: string | null;
}

export type LectureDetail = {
  subject: string;
  runId: string;
  uid: string;
  date: string;
  slot: number;
  slotEnd: number;
  startTime: string;
  title: string;
  professors: string[];
  author: string;
  version: number | null;
  course: string;
  files: LectureFile[];
  /**
   * `conversationUrl`은 관리자 응답에만 있다. 만든 계정에서만 열리는 값이라
   * 서버가 일반 사용자 응답에서 아예 빼고 내려보낸다.
   */
  preview: { provider: PreviewProvider; shareUrl: string; conversationUrl?: string } | null;
  /** 내 개인 예습 대화. 만든 AI 계정에서만 열리므로 남의 것은 안 내려온다. */
  myPreview: { provider: PreviewProvider; conversationUrl: string } | null;
  prequiz: QuizProgress | null;
  /**
   * 복습 웹 풀이. **2026-08-31에 생겼고 그 전에 구운 편에는 없다.**
   * `null`이면 화면이 그 자리를 아예 안 그린다 — 덱만 있는 편과 같다.
   */
  mainquiz: QuizProgress | null;
  runMeta?: Record<string, RunMetaBrief>;
};

/**
 * 예습 카드 한 장. **보기가 없다** — 자유회상이고 채점은 본인이 한다.
 *
 * `answer`도 `explanation`도 여기 없다. 답을 편 사람만 `reveal`로 받아 가고,
 * 그래야 「맞았다」가 무언가를 뜻한다.
 */
/**
 * 무엇을 눌렀나. **안키의 넷이다**(2026-09-18).
 *
 * 그 전에는 Again과 Pass 둘이었고 카드마다 불리언 하나가 남았다. 지금은 이
 * 넷이 다음 때를 정한다 — 정하는 곳은 서버(`app/srs.py`) 하나다.
 */
export const quizGrades = ["again", "hard", "good", "easy"] as const;
export type QuizGrade = (typeof quizGrades)[number];

/**
 * 카드 한 장의 일정. 서버 `_Attempt`의 칼럼과 같다.
 *
 * `null`이면 아직 안 찍은 카드다 — 그 뜻은 「지금 낸다」이므로 화면이
 * 일정을 계산할 일이 없다.
 */
export type QuizSchedule = {
  /** 본인이 맞았다고 했는가. 넷 중 `again`이면 거짓이다. */
  correct: boolean;
  state: "new" | "learning" | "review" | "relearn";
  step: number;
  /** 익은 카드의 간격. 익히는 중이면 0이다. */
  intervalDays: number;
  ease: number;
  reps: number;
  lapses: number;
  /** 언제 다시 내는가. `null`이면 지금이다. */
  dueAt: string | null;
};

export type QuizItem = {
  itemId: string;
  /** 푸는 방식은 셋 다 같다. 화면이 꼴만 달리 그린다. */
  qtype: "basic" | "cloze" | "ox";
  stem: string;
  focus: string;
  cardType: string;
  examHit: boolean;
  attempt: QuizSchedule | null;
};

export type QuizPayload = {
  subject: string;
  runId: string;
  title: string;
  items: QuizItem[];
  answered: number;
  correct: number;
  /**
   * 서버의 지금. **화면의 시계를 믿지 않는다** — 익히는 단계는 분 단위라,
   * 기계 시각이 몇 분 틀어져 있으면 「1분 뒤」가 이미 지난 일이 되거나
   * 영영 안 온다. 화면은 이 값으로 차이를 재서 자기 시계를 보정한다.
   */
  now: string;
  /** 되돌릴 것이 있는가. 없으면 버튼을 아예 안 켠다. */
  undoable: boolean;
};

/** 이 버튼을 누르면 언제 다시 나오나. `days`가 0이면 `seconds`를 읽는다. */
export type NextInterval = { days: number; seconds: number };

/**
 * `reveal`이 주는 것. 펴 보기만으로는 아무것도 기록되지 않는다.
 *
 * `next`는 네 버튼에 적을 값이다. **서버가 재서 보낸다** — 화면이 자기
 * 계산으로 적으면 사다리가 파이썬과 타입스크립트 두 곳에 산다.
 */
export type RevealResult = {
  itemId: string;
  answer: string;
  explanation: string;
  sourceAnchor: string;
  slideNo: number | null;
  slideUrl: string | null;
  next: Record<QuizGrade, NextInterval>;
};

/** `grade`가 돌려주는 것. 찍은 뒤의 일정이라 화면이 큐를 다시 세울 수 있다. */
export type GradeResult = {
  itemId: string;
  grade: QuizGrade;
  correct: boolean;
  attempt: QuizSchedule;
  now: string;
  undoable: boolean;
};

/**
 * `undo`가 돌려주는 것. **답이 펴진 채로 다시 세우는 데 필요한 전부다.**
 *
 * `reveal`을 한 번 더 부르게 두면 누른 뒤에 빈 화면이 한 박자 보인다.
 * `attempt`가 `null`이면 그 찍기가 이 카드의 첫 찍기였다는 뜻이다 — 줄이
 * 사라졌고 카드는 다시 새 카드다.
 */
export type UndoResult = RevealResult & {
  attempt: QuizSchedule | null;
  now: string;
  undoable: boolean;
};

/** 관리자가 강의마다 채우는 다섯 칸. 서버의 `CHECKLIST_ITEMS`와 순서까지 같다. */
export const checklistItems = [
  "notes_prev",
  "preview",
  "pre_apkg",
  "notes_current",
  "main_apkg",
] as const;

export type ChecklistItem = (typeof checklistItems)[number];

/** `waived`는 "이 강의엔 해당 없음"으로 관리자가 닫은 칸이다. */
export type ChecklistState = "done" | "waived" | "todo";

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
export type DeckKind = "pre" | "main";

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
  kind: DeckKind;
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
  kind: DeckKind;
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

/**
 * 구워진 덱 하나의 요약. `run.meta.json`에서 서버가 꺼내 둔 값이다.
 *
 * `sourceVersion`은 **무슨 판으로 구웠나**다. 지금 필기의 판(`AdminRow.version`)이
 * 그보다 크면 그 덱은 옛 자료로 만든 것이고, 한 편의 두 덱 중 하나만 다시 구운
 * 경우가 여기서 갈려 보인다. 파일명을 못 읽으면 `null`이다 — 1로 메우면 「같은
 * 판」으로 읽힌다.
 */
export type RunMetaBrief = {
  reviewFlagged: number;
  slidesUnused: number;
  itemCount: number;
  builtAt: string | null;
  sourceVersion: number | null;
};

export type AdminRow = {
  subject: string;
  runId: string;
  date: string;
  slot: number;
  title: string;
  professors: string[];
  author: string;
  version: number | null;
  match: {
    timetableEventId: string | null;
    confirmed: boolean;
    eventTitle: string | null;
    eventDetails: string | null;
  };
  has: Record<string, boolean>;
  /** 관리자가 채우는 다섯 칸. `done` | `waived` | `todo`. */
  checklist: Record<ChecklistItem, ChecklistState>;
  preItemCount: number;
  /** 이 편의 가장 최근 일감. **갈래를 안 가린다** — 관리 화면은 「러너가 안 붙었는데
   *  기다리는 일감이 있다」만 세므로, 그 수에는 예습도 복습도 같이 들어간다.
   *  끝난 것도 남는다 — 실패가 조용히 사라지면 안 된다. */
  prequizJob: PrequizJob | null;
  preview: { shareUrl: string; conversationUrl: string; provider: PreviewProvider } | null;
  runMeta: Record<string, RunMetaBrief>;
};

export type AdminOverview = {
  lectures: AdminRow[];
  courseAliases: { courseKey: string; course: string; subject: string }[];
  /** 과목으로 볼 만큼 자주 열리는 것만. 한 번짜리 특강·행사는 빠져 있다. */
  timetableCourses: { courseKey: string; course: string; sessions: number }[];
  subjects: string[];
  runner: RunnerBeat | null;
};

/** 사이트에서 카드 한 장에 내린 판정(`server/app/routes/cards.py`). */
export type CardAction = "ok" | "edit" | "delete";

/**
 * 관리자가 보는 카드 한 장 — **답까지 있다.**
 *
 * `flag` 는 걸린 까닭이다. `defect` 는 재현 검사가 문항 결함으로 가른 것이고
 * 2026-09-23 전까지 덱째로 배포를 막던 것, `axis` 는 빈칸이 무엇을 묻는지 안
 * 선 것이고 막은 적은 없다. 그날 전에 만든 편은 사유(`reason`)가 빈다.
 */
export type ReviewCard = {
  subject: string;
  runId: string;
  title: string;
  date: string;
  kind: "pre" | "main";
  itemId: string;
  ord: number;
  qtype: string;
  stem: string;
  /** 빈칸 카드의 원문(`{{c1::…}}`). 빈칸 카드는 이것을 고친다 — 답이 질문 안에 있다.
   *  2026-09-23 전에 올라온 카드는 비어 있고, 그때는 질문을 못 고친다. */
  sourceStem: string;
  answer: string;
  explanation: string;
  slideNo: number | null;
  slideUrl: string | null;
  flags: string[];
  /** 파이프라인이 올린 그대로. 고친 칸과 맞대 보려고 있다. */
  original: { stem: string; sourceStem: string; answer: string; explanation: string };
  flag: { why: "defect" | "axis"; reason: string; note: string; reproduced: string } | null;
  edit: { action: CardAction; editedBy: string; editedAt: string | null } | null;
};

export type CardReview = { cards: ReviewCard[]; open: number; done: number };

export type LectureCards = {
  subject: string;
  runId: string;
  title: string;
  kind: "pre" | "main";
  cards: ReviewCard[];
};
