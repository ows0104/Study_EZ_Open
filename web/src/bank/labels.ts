import { studyDayKey } from "../calendar/entries";

/** 회상 방향의 화면 이름. 풀이 창과 개념 지도가 같이 읽는다. 값은 서버 은행의 `retrieval_direction`. */
export const DIRECTION_LABEL: Record<string, string> = {
  direct: "직접", reverse: "역방향", mechanism: "기전", discrimination: "구별",
  integration: "통합", sequence: "순서", trap: "함정",
};

export function daysLabel(examDate: string) {
  // 학습일(새벽 4시)로 센다. 시각까지 빼면 새벽에 하루가 반올림으로 흔들린다.
  const days = Math.round((Date.parse(`${examDate}T00:00:00+09:00`) - Date.parse(`${studyDayKey()}T00:00:00+09:00`)) / 86_400_000);
  return days > 0 ? `시험까지 D-${days}` : days === 0 ? "오늘 시험" : "시험일 지남";
}
