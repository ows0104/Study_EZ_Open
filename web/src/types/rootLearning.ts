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
export type RootFocus={tiers:RootTierName[]; counts:Record<RootTierName,number>};
/** 강의 목록 카드 열(문항 단위). Quiz Bank `CardProgress`와 같은 단계 이름. */
export type RootQuestionProgress = {total:number; unseen:number; recognized:number; retrieving:number; retained:number; reviewDue:number};
export type RootOverview = {revision:string; title:string; policyReady:boolean; message?:string;
  policy?:RootPolicy; summary:RootSummary|null; plan:RootPlan|null; sessionId:string|null; preparationProblems?:number;
  questionProgress?:RootQuestionProgress;
  /** 오늘 학습 중요도 필터(2026-11-12). plan은 tiers로 거른 결과, counts는 준비된 과제 수(거르기 전). */
  focus?:RootFocus;
  scope?:{label:string; limitations:string[]; included:string[]; excluded:string[]}};
export type RootView = {sessionId:string; revision:string; version:number; day:string; policy:RootPolicy;
  position:number; count:number; finished:boolean; blocked:string|null; canUndo:boolean; mapSeen:boolean; summary:RootSummary;
  task:{id:string; question:BankQuestion; answer:RootAnswer|null; response:string|null; attempted:boolean|null; helped:boolean}|null};
export type RootAnswer = BankAnswer&{reviewNotes?:{source:string;verdict:string;note:string;suggested_answer:string}[];
  reviewIssues?:string[];sourceLinks?:{label:string;url:string}[];pdfSlides?:RootPdfSlide[];
  /** 족보(exam) 원본의 지면. 강의록 슬라이드와 따로 그린다. */
  jokboPdfSlides?:RootPdfSlide[];
  /** 판의 근거 보강이 있어 pdfSlides의 primary가 실제 판정이다. */
  slideFocusKnown?:boolean};
/** Read-only look-ahead of one session position (GET …/prepare). Records nothing; display only until /events confirms. */
export type RootFrame = {position:number; taskId:string; blocked:string|null;
  task:{id:string; question:BankQuestion; answer:RootAnswer; helped:boolean}|null};
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
