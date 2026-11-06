import { studyBlockKey, studyCourseOf } from "../bank/studyBlocks";
import type { TimetableEvent } from "../types/lectures";

/**
 * 표시 갈래와 번호(2026-11 개편). DB의 시간표는 바꾸지 않고 화면에서만 계산한다.
 *
 * 시간표 `category`는 손으로 넣은 값이라 TBL은 lecture, CBL은 practice, 동영상 강의는 lecture로 들어 있다.
 * 사용자 지시(2026-11-05):
 *   - 일반 강의·실습·TBL·CBL은 번호를 따로 센다.
 *   - 동영상 강의는 TBL 예습이라 TBL 쪽에 두고, 같은 주제의 다음 TBL 번호로 「TBL n 영상」.
 *   - 강의 번호는 영상을 뺀 뒤 빈칸 없이 다시 매기고, 블럭(감염과 면역은 1차·2차)마다 1부터.
 */
export type DisplayKind = "lecture" | "practice" | "tbl" | "cbl" | "video" | "exam" | "other";

export const kindLabel: Record<DisplayKind, string> = {
  lecture: "강의",
  practice: "실습",
  tbl: "TBL",
  cbl: "CBL",
  video: "TBL 영상",
  exam: "시험",
  other: "일정",
};

type EventLike = Pick<TimetableEvent, "title" | "details" | "category">;

export function displayKind(event: EventLike): DisplayKind {
  if (event.category === "exam") return "exam";
  if (event.category !== "lecture" && event.category !== "practice") return "other";
  const text = `${event.title} ${event.details}`;
  if (/\bTBL\b/i.test(event.title)) return "tbl";
  if (/\bCBL\b/i.test(event.title)) return "cbl";
  if (/동영상\s*강의/.test(text)) return "video";
  return event.category === "practice" ? "practice" : "lecture";
}

/** 제목 끝의 번호(「감염과 면역 TBL 2」의 2). */
function titleNumber(title: string) {
  const match = title.match(/(\d{1,3})\s*$/);
  return match ? Number(match[1]) : null;
}

export type DisplayInfo = { kind: DisplayKind; code: string; block: string };

const cache = new WeakMap<TimetableEvent[], Map<string, DisplayInfo>>();

/**
 * 시간표 전체 → 칸마다 표시 갈래·번호표·블럭 이름.
 * 강의 번호는 「1」, 그 밖은 「실습 1」·「TBL 1」·「CBL 1」·「TBL 1 영상」. 시험은 번호표 없음.
 */
export function displayInfo(events: TimetableEvent[]): Map<string, DisplayInfo> {
  const hit = cache.get(events);
  if (hit) return hit;
  const out = new Map<string, DisplayInfo>();
  const ordered = [...events].sort((a, b) => a.date.localeCompare(b.date) || a.startTime.localeCompare(b.startTime));
  const counters = new Map<string, number>();
  const next = (block: string, kind: DisplayKind) => {
    const key = `${studyBlockKey(block)}|${kind}`;
    const n = (counters.get(key) ?? 0) + 1;
    counters.set(key, n);
    return n;
  };
  const tbls = ordered.filter(e => displayKind(e) === "tbl");

  for (const event of ordered) {
    const kind = displayKind(event);
    const block = kind === "exam" || kind === "other" ? "" : studyCourseOf(event, events);
    let code = "";
    if (kind === "lecture") code = String(next(block, "lecture"));
    else if (kind === "practice") code = `실습 ${next(block, "practice")}`;
    else if (kind === "tbl") code = `TBL ${titleNumber(event.title) ?? next(block, "tbl")}`;
    else if (kind === "cbl") code = `CBL ${titleNumber(event.title) ?? next(block, "cbl")}`;
    else if (kind === "video") {
      // 같은 블럭에서 이 영상 다음에 오는 TBL이 이 영상의 TBL이다.
      const target = tbls.find(t => t.date >= event.date && studyBlockKey(studyCourseOf(t, events)) === studyBlockKey(block));
      const n = target ? titleNumber(target.title) : null;
      code = n ? `TBL ${n} 영상` : "TBL 영상";
    }
    out.set(event.id, { kind, code, block });
  }
  cache.set(events, out);
  return out;
}

/** 패널·목록에 쓰는 긴 번호표. 강의는 「강의 3」. */
export function fullCode(info: DisplayInfo | undefined) {
  if (!info) return "";
  if (info.kind === "lecture") return `강의 ${info.code}`;
  if (info.kind === "exam") return "시험";
  return info.code || kindLabel[info.kind];
}

/**
 * 시간표 세부 「감염학) 감염질환에 대한 접근」 → 분야 「감염학」 + 제목.
 * 괄호 머리가 없으면 분야는 빈 값이다.
 */
export function splitSubject(raw: string): { subject: string; title: string } {
  // 「<동영상 강의 시청>」 같은 머리표는 번호표(「TBL 1 영상」)가 대신 말한다.
  const detail = raw.replace(/^\s*<[^>]*>\s*/, "");
  const match = detail.match(/^\s*([^\s()]{1,10})\)\s*(.+)$/);
  return match ? { subject: match[1], title: match[2].trim() } : { subject: "", title: detail.trim() };
}
