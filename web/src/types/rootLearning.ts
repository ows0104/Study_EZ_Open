import type { BankAnswer, BankQuestion, BankRating } from './bank';
export type RootPdfSlide = {sourceId:string;sourceSha256:string;sourceFilename:string;page:number;url:string;
  /** API path streaming the same frozen PDF; PDF.js cannot fetch the signed R2 URL (no CORS rule). */
  proxyPath?:string;
  /** Quiz Bank와 같은 내용 대조로 고른 핵심 지면(판의 근거 보강이 있을 때만). */
  primary?:boolean;
  /** 족보 지면의 연도·문항 번호(「2023 79번」). */
  references?:string[]};
export type RootPolicy = {id: string; day_hour: number; deadline_offset: number} & (
  {intervals: number[]} | {mode:'adaptive'; initial_days:number; success_growth:number; partial_factor:number; max_days:number; exam_fraction:number});
export type RootSummary = {total: number; learned: number; recalled: number; unseen: number; unready: number;
  importantUnseen: number; newToday: number; recallChange: number; recallLearningChange:number; recallTimeChange:number;
  /** Main-Quiz 학습률 0~100(서버 root_learning/score.py). 지도 목표가 없으면 null. */
  score?: number | null;
  targets: {id:string; learned:boolean; recalled:boolean; important:boolean; ready:boolean; status:string}[]};
export type RootPlan = {tasks:{task_id:string; direction_id:string; question_id:string; reason:string}[];
  newGoalQuota:number; days:number|null; habitualTasks:number|null; deadline:string|null;
  preparedUnseen:number; unpreparedGoals:number; scopeNote:string};
export const ROOT_TIERS=['Essential','Core','Important','Optional'] as const;
export type RootTierName=typeof ROOT_TIERS[number];
export type RootFocus={tiers:RootTierName[]; counts:Record<RootTierName,number>;
  /** 선행 문항 포함/미포함(2026-11-18-prereq-toggle). 없으면 포함. */
  prereqs?:boolean};
/** 모아풀기 시작 화면(2026-11-18-mix-options). 미열람·복습 대상·나중 — 강의 목록 칸과 같은 단위. */
export type RootMixKind='unseen'|'due'|'later';
export type RootMixOrder='ordered'|'random';
export type RootMixOptions={tiers:RootTierName[]; unseen:boolean; ignoreSchedule:boolean; order:RootMixOrder; prereqs?:boolean};
/** 모아풀기 회차의 묶음(2026-11-19-mix-urgency-order): 앞 due칸은 복습 대상, 다음 unseen칸은 미열람, 나머지는 복습 주기 이전.
 *  urgency는 그 나머지 칸마다 급함 값(작을수록 급함). 옛 회차는 없다. */
export type RootMixPhases={due:number; unseen:number; urgency:number[]};
export type RootMixInfo={revision:string; title:string; counts:Record<RootTierName,Record<RootMixKind,number>>;
  /** 오늘 안 끝난 모아풀기 회차. 같은 조건으로 시작하면 이어 푼다. */
  open:{sessionId:string; options:RootMixOptions; left:number; phases?:RootMixPhases}[];
  /** 오늘 다 푼 모아풀기 회차. 새로고침 전에 끝낸 강의를 마침 화면에 남긴다. 옛 서버는 보내지 않는다. */
  closed?:{sessionId:string; options:RootMixOptions; count:number}[]};
/** 강의 목록 카드 열(문항 단위). Quiz Bank `CardProgress`와 같은 단계 이름. */
export type RootQuestionProgress = {total:number; unseen:number; recognized:number; retrieving:number; retained:number; reviewDue:number};
export type RootOverview = {revision:string; title:string; policyReady:boolean; message?:string;
  policy?:RootPolicy; summary:RootSummary|null; plan:RootPlan|null; sessionId:string|null; preparationProblems?:number;
  questionProgress?:RootQuestionProgress;
  /** 오늘 학습 중요도 필터(2026-11-12). plan은 tiers로 거른 결과, counts는 준비된 과제 수(거르기 전). */
  focus?:RootFocus;
  /** 오늘 학습 흐름에서 지나간 자리 수(2026-11-14 이어 풀기). sessionId가 없고 0보다 크면 오늘 목록을 다 푼 것 → 「더 풀기」. */
  todayDone?:number;
  /** 사진 반입 판(2026-11-15): 시작 화면에 「순서대로/랜덤」을 보인다. order는 진행 중 회차의 지금 순서(없으면 null). */
  orderChoice?:boolean; order?:'ordered'|'random'|null;
  scope?:{label:string; limitations:string[]; included:string[]; excluded:string[]}};
export type RootView = {sessionId:string; revision:string; version:number; day:string; policy:RootPolicy;
  position:number; count:number; finished:boolean; blocked:string|null; canUndo:boolean; mapSeen:boolean; summary:RootSummary;
  /** 이 판에서 내 문제를 만들 수 있다(root-generation/4, 2026-11-15). 옛 서버는 보내지 않는다. */
  mineEnabled?:boolean;
  task:{id:string; question:BankQuestion; answer:RootAnswer|null; response:string|null; attempted:boolean|null; helped:boolean;
    /** 뒤 과제의 문항 선행이라 오늘 목록에 들어왔다(2026-11-16). 옛 서버는 보내지 않는다. */
    prerequisite?:boolean}|null};
export type RootAnswer = BankAnswer&{reviewNotes?:{source:string;verdict:string;note:string;suggested_answer:string}[];
  reviewIssues?:string[];sourceLinks?:{label:string;url:string}[];pdfSlides?:RootPdfSlide[];
  /** 족보(exam) 원본의 지면. 강의록 슬라이드와 따로 그린다. */
  jokboPdfSlides?:RootPdfSlide[];
  /** 판의 근거 보강이 있어 pdfSlides의 primary가 실제 판정이다. */
  slideFocusKnown?:boolean;
  /** 뒷면 「내 메모」(2026-11-15). 나만 본다. 옛 서버는 보내지 않는다(그때는 메모 칸을 그리지 않는다). */
  memo?:string};
/** Read-only look-ahead of one session position (GET …/prepare). Records nothing; display only until /events confirms. */
export type RootFrame = {position:number; taskId:string; blocked:string|null;
  task:{id:string; question:BankQuestion; answer:RootAnswer; helped:boolean; prerequisite?:boolean}|null};
export type RootAction = {kind:'reveal'|'rate'|'skip'|'exclude'|'map'|'undo'; attempted?:boolean; response?:string; helped?:boolean;stimulusHashes?:string[];
  choicesShown?:boolean;
  grade?:'missed'|'partial'|'independent';selfRating?:BankRating};
export type RootMapData = {concepts:{concept_id:string;label:string;parent_ids:string[]}[];
  currentConceptIds?:string[];
  readyDirectionIds?:string[];
  relations:{relation_id:string;from_id:string;to_id:string;kind:string;reason:string}[];
  targets:{target_id:string;title:string;role:string;concept_ids:string[];evidence?:{source_id:string;locator?:string;pages?:number[]}[];
    directions:{direction_id:string;cue:string;answer_scope:string;requirement:string}[];
    importance:Record<string,{status:string;reason:string}>}[];
  points?:{point_id:string;text:string;target_ids:string[];scope_status:string;reason:string}[];
  coverage?:{point_id:string;status:string;reason:string;confirmed_direction_ids:string[];missing_direction_ids:string[];unknown_direction_ids:string[];partial_direction_ids:string[]}[];
  scope:{label:string;limitations:string[]}};
