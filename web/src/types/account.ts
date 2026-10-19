/** 로그인 직후 무엇을 그릴지 정하는 값. 승인 게이트를 지나지 않는 응답이다. */
export type Me = {
  id: string;
  email: string;
  isAdmin: boolean;
  isApproved: boolean;
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
  bank?: { cards: number; selfCorrect: number; grades: number };
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
