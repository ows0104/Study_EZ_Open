/**
 * 학생이 누르는 「문제 있음」의 갈래. 서버가 받는 값은 `server/app/routes/bank.py` 의
 * `FEEDBACK_CATEGORIES` 이고, 그중 `good`(좋은 문제)은 신고가 아니라서 여기 없다.
 *
 * 두 자리가 읽는다 — 풀이 창의 신고 폼(`BankStudy.tsx`)과 관리 화면 「Quiz Bank 신고」 탭.
 * 두 화면은 따로 늦게 불러지므로(lazy) 한쪽이 다른 쪽을 import 하지 않게 여기 둔다.
 */
export const FEEDBACK = [
  ["content", "내용 오류"], ["wording", "발문 애매"], ["leak", "정답 누설"], ["format", "형식 부적절"],
  ["burden", "답이 너무 많다"], ["easy", "너무 쉬움"], ["hard", "너무 어려움"], ["duplicate", "중복"],
  ["other", "기타"],
] as const;

export const FEEDBACK_LABEL: Record<string, string> = Object.fromEntries(FEEDBACK);
