/**
 * 강조색 다섯 조합(2026-11-05 사용자 지시, 2026-11-06 운영 적용 승인).
 *
 *   메인   = 지금·복습·주요 선택 (선택된 메뉴, 오늘, 지금 선, 복습 학습률·버튼)
 *   두 번째 = 예습 (예습 퀴즈 완료 토막, 예습 버튼, 미열람 예습)
 *
 * 2026-08-31 관리자 지시의 갈래 고정색(`--fam-*`)을 이 두 색으로 대체한다.
 * 시험·D-day·신규 교수 N은 조합과 무관하게 빨강(`--exam`)이다.
 * 고른 값은 이 기기의 localStorage에만 둔다.
 */
export const ACCENTS = [
  { id: "indigo", name: "인디고 + 앰버", accent: "#3e63dd", ink: "#2f4fb8", accent2: "#e8930c", ink2: "#a35f00" },
  { id: "blue", name: "블루 + 민트", accent: "#1677ff", ink: "#0b5fd1", accent2: "#10a37f", ink2: "#0b7a5f" },
  { id: "clay", name: "클레이 + 슬레이트 블루", accent: "#d97757", ink: "#b65a3b", accent2: "#4f7cb8", ink2: "#355f96" },
  { id: "red", name: "토마토 + 바이올렛", accent: "#dc4c3e", ink: "#b8382c", accent2: "#7856d6", ink2: "#5a3db3" },
  { id: "green", name: "그린 + 머스터드", accent: "#1f8a5b", ink: "#176b46", accent2: "#d9a400", ink2: "#8a6700" },
] as const;

export type AccentId = (typeof ACCENTS)[number]["id"];

const KEY = "studyez-accent";

export function loadAccent(): AccentId {
  try {
    const raw = localStorage.getItem(KEY);
    return ACCENTS.find(a => a.id === raw)?.id ?? "indigo";
  } catch {
    return "indigo";
  }
}

/** 문서 뿌리에 조합을 입힌다. 옅은 바탕·선은 CSS가 표면 색에 섞어 만든다(다크 모드도 따라온다). */
export function applyAccent(id: AccentId = loadAccent()) {
  const a = ACCENTS.find(x => x.id === id) ?? ACCENTS[0];
  const root = document.documentElement.style;
  root.setProperty("--theme-accent", a.accent);
  root.setProperty("--theme-accent-ink", a.ink);
  root.setProperty("--theme-accent2", a.accent2);
  root.setProperty("--theme-accent2-ink", a.ink2);
}

export function saveAccent(id: AccentId) {
  try {
    localStorage.setItem(KEY, id);
  } catch {
    /* 저장이 막혀도 이번 화면에는 적용한다 */
  }
  applyAccent(id);
}
