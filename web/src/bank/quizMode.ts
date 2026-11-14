/**
 * 복습 퀴즈(Main-Quiz) 풀이 모드(2026-11-14 사용자 지시, docs/changes/2026-11-14-mcq-mode).
 * recall: 지금처럼 주관식. mcq: 선지가 있는 모든 문항을 객관식으로(정답 개수는 알리지 않고 고른 뒤 Space로 확인).
 * 이 기기 브라우저에만 보관하는 편의 설정이다. 못 읽으면 주관식으로 동작한다.
 */
import type { BankQuestion } from '../types/bank';
import type { RootAnswer } from '../types/rootLearning';

export type QuizMode = 'recall' | 'mcq';
const KEY = 'studyez:main-quiz-mode';

export function readQuizMode(): QuizMode {
  try { return localStorage.getItem(KEY) === 'mcq' ? 'mcq' : 'recall'; } catch { return 'recall'; }
}

export function saveQuizMode(mode: QuizMode) {
  try { localStorage.setItem(KEY, mode); } catch { /* 이번 화면에서는 고른 대로 동작한다. */ }
}

type Choice = { id: string; text: string };
const OX: Choice[] = [{ id: 'O', text: 'O' }, { id: 'X', text: 'X' }];

/**
 * 객관식 모드에서 이 문항에 보일 선지와 (답을 본 뒤) 정답 ID. 선지가 없으면 null(그 문항은 주관식으로 푼다).
 * 문항 자체 선지(mcq·multi_select) → 객관식 모드 선지 → OX → 단답·나열 「선지 보기」 선지 순으로 쓴다.
 */
export function mcqChoices(q: BankQuestion, answer: RootAnswer | null): { choices: Choice[]; correct: string[] | undefined } | null {
  if (q.options.length) return { choices: q.options, correct: answer?.correctOptionIds };
  if (q.mcq_choices?.length) return { choices: q.mcq_choices, correct: answer?.mcqCorrectIds };
  if (q.format === 'ox') {
    const right = answer?.answer.trim().toUpperCase();
    return { choices: OX, correct: answer ? (right === 'O' || right === 'X' ? [right] : []) : undefined };
  }
  if (q.recall_choices?.length) return { choices: q.recall_choices, correct: answer?.recallCorrectIds };
  return null;
}

/**
 * 주관식에서 「선지 보기」(V)로 펴는 선지. 객관식 모드와 같은 선지를 먼저 쓰고(2026-11-14 choices-merge), 없으면 예전 「선지 보기」 선지.
 * 문항 자체 선지가 있는 문항은 대상이 아니다(그 선지가 그대로 보인다).
 */
export function recallChoices(q: BankQuestion, answer: RootAnswer | null): { choices: Choice[]; correct: string[] | undefined } | null {
  if (q.options.length) return null;
  if (q.mcq_choices?.length) return { choices: q.mcq_choices, correct: answer?.mcqCorrectIds };
  if (q.recall_choices?.length) return { choices: q.recall_choices, correct: answer?.recallCorrectIds };
  return null;
}
