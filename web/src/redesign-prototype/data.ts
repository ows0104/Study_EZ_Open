/**
 * 개편 프로토타입의 시간표.
 *
 * 「2026년 1학년 감염과 면역 시간표 학생공지.pdf」(11.2–11.27)를 옮겨 적었다.
 * 운영 API·DB를 부르지 않는다. 학습률·회독은 날짜로 찍어 낸 가짜 값이다.
 *
 * 번호는 갈래마다 따로 센다(2026-11-05 사용자 지시):
 *   강의 1차 1–46 · 2차 1–18 · 실습 1–4 · TBL 1–2(+영상 2) · CBL 1–9 · 임상의학입문 1–4(같은 시간대의 다른 과목).
 *   강의 번호는 동영상 강의(시간표 「감염과 면역 5·14」)를 TBL로 옮긴 뒤 빈칸 없이 다시 매긴다(2026-11-05 사용자 지시).
 *   아래 표의 강의 번호는 시간표 원래 번호이고, 화면 번호는 build()가 날짜순으로 새로 센다.
 *   시간표에 번호가 없는 「미생물학 실습: 세균의 분리 1–3」은 실습 2–4,
 *   매주 「임상의학입문 1」로 적힌 화요일 오후는 주차 순서대로 1–4로 셌다.
 */

export type Category = 'lecture' | 'practice' | 'tbl' | 'cbl' | 'intro' | 'exam';

/** Quiz Bank 카드 단계(운영 web/src/bank/StudyOverview.tsx와 같은 네 단계). due = 오늘 복습할 카드 */
export type Cards = { total: number; unseen: number; recognized: number; retrieving: number; retained: number; due: number };

export type Entry = {
  id: string;
  date: string; // YYYY-MM-DD
  start: string; // HH:MM
  end: string;
  category: Category;
  /** 갈래 안의 번호. 시험은 차수 */
  no: number;
  /** 칸에 붙이는 짧은 번호표. 강의는 숫자만 */
  code: string;
  title: string;
  /** 감염학·미생물학 같은 분야. 시간표에 없으면 빈 값 */
  subject: string;
  professor: string;
  /**
   * 교수 변경 표시(2026-11-05 사용자 지시). null = 작년과 같은 교수이거나 판정 없음,
   * '23' 같은 두 자리 = 작년과 다르지만 최근 5년 안에 맡은 가장 최근 연도, 'N' = 최근 5년 담당 기록 없음.
   */
  profNote: string | null;
  block: string;
  /** 예습 퀴즈 문항 수. null = 예습 퀴즈 없음 */
  preTotal: number | null;
  /** 예습 퀴즈를 끝까지 풀었는가(자동 기록). 예습은 1회독까지만 센다(2026-11-05 사용자 지시) */
  preDone: boolean;
  /** 시작했지만 끝내지 않았을 때 푼 문항. 표시에는 색을 쓰지 않고 이어 풀기 안내에만 쓴다 */
  prePartial: number;
  /** 강의록 회독(자가 기록) 기본값. 화면에서 더하고 뺀 값은 노트 저장소가 덧입힌다 */
  noteReads: number;
  /** 복습 학습도. null = 아직 열리지 않았거나 복습이 없음 */
  review: number | null;
  /** 복습 카드. null = 퀴즈 없음(TBL·CBL·다른 과목·시험) */
  cards: Cards | null;
};

/** 프로토타입의 "오늘". 화면이 날마다 달라지지 않게 고정한다. */
export const TODAY = new Date('2026-11-05T10:20:00');

/**
 * 감염과 면역은 1차·2차 시험 범위의 과목이 전혀 달라 블럭을 나눈다(2026-11-05 사용자 지시).
 * 1차 = 11.2–11.20(1차 시험까지), 2차 = 11.23–11.27(2차 시험까지). 강의 번호는 블럭마다 1부터 센다(1차 1–46, 2차 1–18).
 */
export const BLOCK1 = '감염과 면역 1차';
export const BLOCK2 = '감염과 면역 2차';
export const CURRENT_BLOCK = BLOCK1;
const BLOCK2_START = '2026-11-23';

/* 시간표 원문. [날짜, 시작, 끝, 갈래, 번호, 분야, 제목, 교수] */
type Row = [string, string, string, Category, number, string, string, string];

const A = (a: string, b: string) => `A ${a} / B ${b}`;

/**
 * 교수 변경 판정 결과. 팀원 작업(master `docs/changes/2026-11-05-professor-aware-preview/audit.md`,
 * 운영 `previewSource`의 changed·newProfessor·selected.year)을 강의 제목으로 옮겼다.
 * 작년(2025)과 같은 교수는 표시하지 않는다. 2024 자료는 없어서 연도는 「보유 자료 기준」이다.
 * 자동 확정하지 못한 14칸(합본·실습·평가·미상 등)은 표시하지 않는다.
 */
const PROF_NOTE: Record<string, string> = {
  포도알균: '23',
  사슬알균: '23',
  무산소성세균: 'N',
  간염바이러스: '23',
  '소아 감염': '22',
  '감염병의 집단발병 역학조사': '23',
  '감염병의 예방원칙': '22',
  '전신 경화증': '23',
  '알레르기 비염': '22',
  '두드러기/혈관부종/아나필락시스': 'N',
  '다양한 알레르기질환': 'N',
};
const profNoteFor = (category: Category, title: string) =>
  category === 'lecture' ? PROF_NOTE[title] ?? null : null;

const TIMETABLE: Row[] = [
  // 1주차
  ['11-02', '09:00', '09:50', 'lecture', 1, '감염학', '감염질환에 대한 접근', '김남중'],
  ['11-02', '10:00', '10:50', 'lecture', 2, '감염학', '감염병의 병인론', '최은화'],
  ['11-02', '11:00', '11:50', 'lecture', 3, '감염학', '감염병의 진단', '김택수'],
  ['11-02', '13:00', '13:50', 'lecture', 4, '감염학', '감염병의 치료 원칙', '김홍빈'],
  // 동영상 강의(시간표의 「감염과 면역 5·14」)는 TBL 예습이라 TBL 쪽으로 둔다(2026-11-05 사용자 지시).
  ['11-02', '14:00', '15:50', 'tbl', 1, '', '동영상: 위장관 감염, 피부연조직감염, 요로감염, 폐렴', ''],
  ['11-03', '09:00', '11:50', 'tbl', 1, '감염학', '위장관감염, 피부연조직감염, 요로감염, 폐렴', A('박완범·오홍상', '최평균·윤기욱')],
  ['11-03', '13:00', '16:50', 'intro', 1, '', '임상의학입문', ''],
  ['11-04', '09:00', '09:50', 'lecture', 6, '미생물학', '포도알균', '김범준'],
  ['11-04', '10:00', '10:50', 'lecture', 7, '병리학', '감염성 질환의 병리 1', '김지은'],
  ['11-04', '11:00', '11:50', 'lecture', 8, '병리학', '감염성 질환의 병리 2', '김지은'],
  ['11-04', '13:00', '15:50', 'practice', 1, '병리학', '감염 병리 통합실습', '김지은'],
  ['11-05', '09:00', '09:50', 'lecture', 9, '미생물학', '사슬알균', '김범준'],
  ['11-05', '10:00', '10:50', 'lecture', 10, '미생물학', '장내세균의 일반적 특성', '김동현'],
  ['11-05', '11:00', '11:50', 'lecture', 11, '미생물학', '장내세균: 기회감염균, 장병원성균', '김동현'],
  ['11-05', '13:00', '13:50', 'lecture', 12, '미생물학', '콜레라, 캄필로박터, 수도모나스', '방예지'],
  ['11-05', '14:00', '14:50', 'lecture', 13, '미생물학', '미코플라스마, 클라미디아', '김동현'],
  ['11-05', '15:00', '15:50', 'tbl', 2, '', '동영상: 심내막염, 중추신경계감염', ''],
  ['11-06', '09:00', '10:50', 'tbl', 2, '감염학', '심내막염, 중추신경계감염', A('강창경·김택수', '문송미·이찬미')],
  ['11-06', '11:00', '11:50', 'lecture', 15, '미생물학', '미코박테리움', '염진기'],
  ['11-06', '13:00', '13:50', 'lecture', 16, '미생물학', '코리네박테리움, 노카르디아', '염진기'],
  ['11-06', '14:00', '14:50', 'lecture', 17, '미생물학', '무산소성세균', '염진기'],
  // 2주차
  ['11-09', '09:00', '09:50', 'lecture', 18, '미생물학', '헤모필루스, 보르데텔라, 나이세리아', '방예지'],
  ['11-09', '10:00', '10:50', 'lecture', 19, '미생물학', '레지오넬라, 리스테리아, 바실루스', '석승혁'],
  ['11-09', '11:00', '11:50', 'lecture', 20, '약리학', '항생제 약리학의 기본 원리: 항생제 내성', '이승환'],
  ['11-09', '13:00', '13:50', 'lecture', 21, '감염학', '항생제 내성균의 진단과 치료', '송경호'],
  ['11-09', '14:00', '15:50', 'cbl', 1, '감염학', '세균 감염', A('문송미', '강창경')],
  ['11-10', '09:00', '09:50', 'lecture', 22, '미생물학', '렙토스피라, 매독균, 보렐리아', '김현제'],
  ['11-10', '10:00', '10:50', 'lecture', 23, '미생물학', '아데노바이러스, 폭스바이러스', '방예지'],
  ['11-10', '11:00', '11:50', 'lecture', 24, '미생물학', '리케차', '조남혁'],
  ['11-10', '13:00', '16:50', 'intro', 2, '', '임상의학입문', ''],
  ['11-11', '09:00', '09:50', 'lecture', 25, '미생물학', '파르보바이러스', '김현제'],
  ['11-11', '10:00', '10:50', 'lecture', 26, '미생물학', '피코르나바이러스', '조남혁'],
  ['11-11', '11:00', '11:50', 'cbl', 2, '감염학', '감염성 발진', A('이찬미', '이현주')],
  ['11-11', '13:00', '16:50', 'practice', 2, '미생물학', '세균의 분리 1', ''],
  ['11-12', '09:00', '09:50', 'lecture', 27, '미생물학', '오소믹소바이러스', '조남혁'],
  ['11-12', '10:00', '10:50', 'lecture', 28, '미생물학', '파라믹소/풍진바이러스', '조남혁'],
  ['11-12', '11:00', '11:50', 'lecture', 29, '미생물학', '간염바이러스', '김범준'],
  ['11-12', '13:00', '16:50', 'practice', 3, '미생물학', '세균의 분리 2', ''],
  ['11-13', '09:00', '09:50', 'lecture', 30, '미생물학', '헤르페스바이러스과', '김현제'],
  ['11-13', '10:00', '10:50', 'lecture', 31, '감염학', '소아 감염', '윤기욱'],
  ['11-13', '11:00', '11:50', 'cbl', 3, '감염학', '바이러스 감염', A('윤기욱', '이찬미')],
  ['11-13', '13:00', '16:50', 'practice', 4, '미생물학', '세균의 분리 3', ''],
  // 3주차
  ['11-16', '09:00', '09:50', 'lecture', 32, '미생물학', '신종, 재출현 바이러스', '조남혁'],
  ['11-16', '10:00', '10:50', 'lecture', 33, '미생물학', '토가바이러스, 플라비바이러스', '염진기'],
  ['11-16', '11:00', '11:50', 'lecture', 34, '미생물학', '필로바이러스, 분야바이러스', '염진기'],
  ['11-16', '13:00', '13:50', 'lecture', 35, '미생물학', '진균감염; 캔디다, 폐포자충', '김남중'],
  ['11-16', '14:00', '14:50', 'lecture', 36, '미생물학', '아스페르길루스, 크립토코쿠스, 털곰팡이, 피부진균감염', '김남중'],
  ['11-16', '15:00', '16:50', 'cbl', 4, '감염학', '인수공통 감염/침습성 진균 감염', A('최평균', '오홍상')],
  ['11-17', '09:00', '09:50', 'lecture', 37, '미생물학', '랍도바이러스, 지발바이러스', '석승혁'],
  ['11-17', '10:00', '10:50', 'lecture', 38, '미생물학', '파필로마바이러스, 폴리오마바이러스', '김현제'],
  ['11-17', '11:00', '11:50', 'lecture', 39, '미생물학', '레트로바이러스', '김현제'],
  ['11-17', '13:00', '16:50', 'intro', 3, '', '임상의학입문', ''],
  ['11-18', '09:00', '09:50', 'lecture', 40, '감염학', '의료관련감염', '김의석'],
  ['11-18', '10:00', '10:50', 'lecture', 41, '감염학', '방어기전손상환자의 감염', '최평균'],
  ['11-18', '11:00', '11:50', 'cbl', 5, '감염학', '방어기전손상환자의 감염', A('박완범', '최평균')],
  ['11-18', '13:00', '13:50', 'lecture', 42, '미생물학', '레오바이러스, 코로나바이러스, 노로바이러스', '조남혁'],
  ['11-18', '14:00', '16:50', 'cbl', 6, '미생물학', '미생물학교실 CBL', '미생물학교실'],
  ['11-19', '09:00', '09:50', 'lecture', 43, '예방의학', '감염병의 자연사와 감시, 관리 및 예방', '박수경'],
  ['11-19', '10:00', '10:50', 'lecture', 44, '예방의학', '감염병의 집단발병 역학조사', '박수경'],
  ['11-19', '11:00', '11:50', 'lecture', 45, '감염학', '감염병의 예방원칙', '최은화'],
  ['11-19', '13:00', '13:50', 'lecture', 46, '', '형성평가와 피드백', '박완범'],
  ['11-19', '14:00', '14:50', 'lecture', 47, '감염학', '신종 감염병에 대한 대처와 전망', '박상원'],
  ['11-19', '15:00', '15:50', 'lecture', 48, '감염학', '감염병의 예방: 환경 관리', '신수'],
  ['11-20', '09:00', '11:50', 'exam', 1, '', '감염과 면역 1차 시험', ''],
  // 4주차
  ['11-23', '09:00', '09:50', 'lecture', 49, '', '면역약리학', '이창한'],
  ['11-23', '10:00', '10:50', 'lecture', 50, '', '통풍 관절염', '신기철'],
  ['11-23', '11:00', '11:50', 'lecture', 51, '', '척추 관절염', '이은영'],
  ['11-23', '13:00', '13:50', 'lecture', 52, '', '류마티스 관절염', '이은봉'],
  ['11-23', '14:00', '14:50', 'lecture', 53, '', '전신 홍반 루프스', '하유정'],
  ['11-23', '15:00', '15:50', 'lecture', 54, '', '쇼그렌 증후군', '이윤종'],
  ['11-24', '09:00', '09:50', 'lecture', 55, '', '전신 경화증', '박준원'],
  ['11-24', '10:00', '10:50', 'lecture', 56, '', '피부근염', '강은하'],
  ['11-24', '11:00', '11:50', 'lecture', 57, '', '혈관염', '박진균'],
  ['11-24', '13:00', '16:50', 'intro', 4, '', '임상의학입문', ''],
  ['11-25', '09:00', '09:50', 'lecture', 58, '', '알레르기질환의 병인론', '강혜련'],
  ['11-25', '10:00', '10:50', 'lecture', 59, '', '알레르기 비염', '장윤석'],
  ['11-25', '11:00', '11:50', 'lecture', 60, '', '기관지 천식', '박흥우'],
  ['11-25', '13:00', '13:50', 'lecture', 61, '', '소아 천식', '김경훈'],
  ['11-25', '14:00', '14:50', 'lecture', 62, '', '암면역', '성승용'],
  ['11-25', '15:00', '15:50', 'cbl', 7, '', '암면역', A('김태민', '김범석')],
  ['11-26', '09:00', '09:50', 'lecture', 63, '', '두드러기/혈관부종/아나필락시스', '강성윤'],
  ['11-26', '10:00', '10:50', 'lecture', 64, '', '약물 알레르기', '김영찬'],
  ['11-26', '11:00', '11:50', 'lecture', 65, '', '다양한 알레르기질환', '양민석'],
  ['11-26', '13:00', '13:50', 'lecture', 66, '', '호산구성 질환', '김세훈'],
  ['11-26', '14:00', '14:50', 'cbl', 8, '', '천식', A('김세훈', '강혜련')],
  ['11-26', '15:00', '15:50', 'cbl', 9, '', '류마티스관절염', A('김민정', '하유정')],
  ['11-27', '14:00', '15:50', 'exam', 2, '', '감염과 면역 2차 시험', ''],
];

export const codeLabel: Record<Category, string> = {
  lecture: '강의',
  practice: '실습',
  tbl: 'TBL',
  cbl: 'CBL',
  intro: '임상의학입문',
  exam: '시험',
};

function codeFor(category: Category, no: number, title = '') {
  if (category === 'tbl' && title.startsWith('동영상')) return `TBL ${no} 영상`;
  if (category === 'lecture') return String(no);
  if (category === 'intro') return `임상 ${no}`;
  if (category === 'exam') return `${no}차`;
  return `${codeLabel[category]} ${no}`;
}

/** 같은 문자열이면 같은 숫자. 학습률을 흔들리지 않게 찍는다. */
function hash(text: string) {
  // FNV-1a + 마무리 섞기. 끝 글자만 다른 id(강의 1, 2, …)도 값이 고르게 흩어진다.
  let h = 2166136261;
  for (const ch of text) h = Math.imul(h ^ ch.charCodeAt(0), 16777619);
  h ^= h >>> 16;
  h = Math.imul(h, 0x85ebca6b);
  h ^= h >>> 13;
  return h >>> 0;
}

function minutesOf(time: string) {
  const [h, m] = time.split(':').map(Number);
  return h * 60 + m;
}

/** 학습 정도 r(0~1)에서 카드 단계를 찍는다. 학습률은 단계에서 다시 계산해 숫자끼리 맞게 한다. */
function cardsFor(h: number, total: number, r: number | null): { cards: Cards; review: number | null } {
  if (r === null) return { cards: { total, unseen: total, recognized: 0, retrieving: 0, retained: 0, due: 0 }, review: null };
  const seen = Math.min(total, Math.round(total * Math.min(1, 0.3 + r * 0.9)));
  const retained = Math.round(seen * r * 0.85);
  const retrieving = Math.round((seen - retained) * 0.7);
  const recognized = seen - retained - retrieving;
  const due = Math.min(seen, Math.round(seen * (0.06 + (1 - r) * 0.3) + (h % 3)));
  const review = (recognized * 0.25 + retrieving * 0.6 + retained) / total;
  return { cards: { total, unseen: total - seen, recognized, retrieving, retained, due }, review };
}

/** 지난 수업일수록 많이 공부했다. 날짜·번호로 찍어서 새로고침해도 같다. */
function learning(key: string, start: string, end: string, category: Category, id: string) {
  const learnable = category === 'lecture' || category === 'practice';
  const preTotal = learnable ? (category === 'practice' ? 12 : 20) : null;
  if (!learnable) return { preTotal, preDone: false, prePartial: 0, noteReads: 0, review: null, cards: null };
  const h = hash(id);
  const todayKey = toKey(TODAY);
  const nowMin = TODAY.getHours() * 60 + TODAY.getMinutes();
  const ended = key < todayKey || (key === todayKey && minutesOf(end) <= nowMin);
  const started = ended || (key === todayKey && minutesOf(start) <= nowMin);
  const daysAhead = Math.round((Date.parse(`${key}T12:00:00`) - Date.parse(`${todayKey}T12:00:00`)) / 86400000);

  let preDone = false;
  let prePartial = 0;
  if (ended) {
    // 지난 강의도 다섯에 하나는 예습 퀴즈를 끝내지 않았다.
    preDone = h % 5 !== 0;
    if (!preDone && h % 2) prePartial = 4 + (h % 11);
  } else if (started || daysAhead <= 1) {
    // 오늘·내일 강의: 끝냈거나, 하다 말았거나, 아직 안 했다.
    if (h % 3 === 1) preDone = true;
    else if (h % 3 === 2) prePartial = 3 + (h % 12);
  }
  const noteReads = ended ? h % 4 : 0;
  // 오래된 강의일수록 복습이 많이 되어 있다.
  const age = Math.min(1, Math.max(0, -daysAhead) / 14);
  const r = ended ? Math.min(1, 0.05 + ((h >>> 3) % 50) / 100 + age * 0.45) : null;
  const total = category === 'practice' ? 14 + (h % 10) : 28 + ((h >>> 5) % 30);
  return { preTotal, preDone, prePartial, noteReads, ...cardsFor(h, total, r) };
}

function build(): Entry[] {
  // 블럭마다 1부터 센다(2026-11-05 사용자 선택: 2차는 1부터).
  const lectureNo: Record<string, number> = {};
  return TIMETABLE.map(([md, start, end, category, sourceNo, subject, title, professor]) => {
    const date = `2026-${md}`;
    const video = title.startsWith('동영상');
    // id는 시간표 원래 번호로 고정한다. 화면 번호만 다시 센다.
    const id = `${date}-${category}-${sourceNo}${video ? '-video' : ''}`;
    const block = category === 'intro' ? '임상의학입문' : date >= BLOCK2_START ? BLOCK2 : BLOCK1;
    const no = category === 'lecture' ? (lectureNo[block] = (lectureNo[block] ?? 0) + 1) : sourceNo;
    return {
      id,
      date,
      start,
      end,
      category,
      no,
      code: codeFor(category, no, title),
      title: category === 'intro' ? `${title} ${no}` : video ? title.replace(/^동영상:\s*/, '') : title,
      subject,
      professor,
      profNote: profNoteFor(category, title),
      // 임상의학입문은 같은 시간대의 다른 과목이다.
      block,
      ...learning(date, start, end, category, id),
    };
  });
}

const ALL_ENTRIES = build();

/* ───────── 지난 블럭(목록 화면의 블럭 선택용 예시) ───────── */

export type Block = { id: string; name: string; range: string; current?: boolean; next?: boolean; timetable?: boolean };

export const BLOCKS: Block[] = [
  { id: 'infection-2', name: BLOCK2, range: '11.23 – 11.27', next: true, timetable: true },
  { id: 'infection-1', name: BLOCK1, range: '11.2 – 11.20', current: true, timetable: true },
  { id: 'neuro', name: '신경과학', range: '10.5 – 10.30' },
  { id: 'msk', name: '근골격과 피부', range: '9.7 – 10.2' },
];

export const CURRENT = BLOCKS.find((b) => b.current)!;

/** 지난 블럭은 실제 시간표가 아니라 목록 모양을 보이기 위한 예시다. */
const PAST: Record<string, { start: string; titles: [string, string][] }> = {
  neuro: {
    start: '2026-10-05',
    titles: [
      ['해부학', '대뇌 피질의 구조'], ['생리학', '활동전위와 시냅스 전달'], ['해부학', '뇌줄기와 뇌신경'],
      ['생리학', '감각 신경로'], ['생리학', '운동 신경로'], ['약리학', '진통제와 마취제'],
      ['병리학', '뇌혈관 질환'], ['신경과학', '기저핵과 소뇌'], ['약리학', '항경련제'],
      ['병리학', '신경퇴행성 질환'], ['신경과학', '수면과 각성'], ['약리학', '항정신병 약물'],
    ],
  },
  msk: {
    start: '2026-09-07',
    titles: [
      ['해부학', '상지의 근육'], ['해부학', '하지의 근육'], ['생리학', '근육 수축'],
      ['조직학', '뼈와 연골'], ['병리학', '뼈 종양'], ['조직학', '피부의 구조'],
      ['병리학', '염증성 피부 질환'], ['약리학', '근이완제'], ['해부학', '척주와 관절'],
      ['병리학', '근육병'],
    ],
  },
};

function pastEntries(blockId: string, blockName: string): Entry[] {
  const past = PAST[blockId];
  if (!past) return [];
  const start = new Date(`${past.start}T12:00:00`);
  return past.titles.map(([subject, title], i) => {
    const date = toKey(addDays(start, Math.floor(i / 3)));
    const startTime = ['09:00', '10:00', '11:00'][i % 3];
    const id = `${blockId}-${i + 1}`;
    const h = hash(id);
    return {
      id,
      date,
      start: startTime,
      end: startTime.replace(':00', ':50'),
      category: 'lecture' as const,
      no: i + 1,
      code: String(i + 1),
      title,
      subject,
      professor: '',
      profNote: null,
      block: blockName,
      preTotal: 20,
      preDone: true,
      prePartial: 0,
      noteReads: 1 + (h % 3),
      ...cardsFor(h, 28 + ((h >>> 5) % 30), Math.min(1, 0.5 + ((h >>> 3) % 50) / 100)),
    };
  });
}

export function blockEntries(blockId: string): Entry[] {
  const block = BLOCKS.find((b) => b.id === blockId) ?? CURRENT;
  if (block.timetable) return ALL_ENTRIES.filter((e) => e.block === block.name);
  return pastEntries(block.id, block.name);
}

/* ───────── 날짜 ───────── */

export function toKey(d: Date) {
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${d.getFullYear()}-${m}-${day}`;
}

export function addDays(d: Date, n: number) {
  const next = new Date(d);
  next.setDate(next.getDate() + n);
  return next;
}

export function startOfWeek(d: Date) {
  const day = (d.getDay() + 6) % 7; // 월요일 = 0
  const next = new Date(d.getFullYear(), d.getMonth(), d.getDate(), 12);
  next.setDate(next.getDate() - day);
  return next;
}

export function entriesBetween(start: Date, end: Date): Entry[] {
  const from = toKey(start);
  const to = toKey(end);
  return ALL_ENTRIES.filter((e) => e.date >= from && e.date <= to);
}

export const categoryLabel: Record<Category, string> = {
  lecture: '강의',
  practice: '실습',
  tbl: 'TBL',
  cbl: 'CBL',
  intro: '다른 과목',
  exam: '시험',
};

export const weekdayLabels = ['월', '화', '수', '목', '금'];

