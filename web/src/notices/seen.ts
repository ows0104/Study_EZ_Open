/**
 * 「새 공지」 점. **서버에 읽음을 두지 않는다** — 이 브라우저가 마지막으로 본
 * 공지 번호만 들고 있다가, 그보다 큰 번호가 오면 머리줄에 점을 찍는다.
 *
 * 기기를 바꾸면 한 번 더 뜨는 정도는 감수한다. 그걸 막자고 사람마다 읽음 표를
 * 세우는 것은 공지 하나에 비해 무겁다. 저장소가 막힌 브라우저(사생활 창 등)에서는
 * 점이 늘 뜰 뿐이고 공지 자체는 그대로 읽힌다.
 */
const KEY = "studyez.noticeSeen";

export function seenNotice(): number {
  try {
    return Number(localStorage.getItem(KEY)) || 0;
  } catch {
    return 0;
  }
}

export function markNoticeSeen(id: number) {
  try {
    if (id > seenNotice()) localStorage.setItem(KEY, String(id));
  } catch {
    /* 저장소가 막혀 있으면 점만 남는다 */
  }
}
