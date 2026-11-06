import { useEffect, useState } from 'react';

/**
 * 메인 컬러 후보와 짝이 되는 두 번째 강조색.
 *
 * 역할을 나눈다:
 *   메인   = 지금·복습 (선택된 메뉴, 주요 버튼, 오늘, 지금 선, 복습 학습도 막대, 복습 대기, 패널의 복습 묶음)
 *   두 번째 = 예습 (예습 퀴즈 회독 네모, 예습 남은 강의, 예습 안 한 강의 점, 패널의 예습 묶음)
 * 복습이 예습보다 중요해서 메인 색을 복습에 쓴다(2026-11-05 사용자 지시). 실습 칸은 회색이다.
 * 시험 칸은 어느 조합에서도 검정이다.
 *
 * accent = 칠하는 색, ink = 옅은 바탕 위 글자·눌린 버튼 색. 옅은 바탕·선은 CSS가 흰색에 섞어 만든다.
 */
export const ACCENTS = [
  {
    id: 'indigo', name: '인디고 + 앰버', from: '현재 Study_EZ · Quiz Bank 주황',
    accent: '#3e63dd', ink: '#2f4fb8', accent2: '#e8930c', ink2: '#a35f00',
  },
  {
    id: 'blue', name: '블루 + 민트', from: 'OpenAI Platform 아이콘 파랑 · OpenAI 초록',
    accent: '#1677ff', ink: '#0b5fd1', accent2: '#10a37f', ink2: '#0b7a5f',
  },
  {
    id: 'clay', name: '클레이 + 슬레이트 블루', from: 'Claude 로고 · 「Upgrade」 파랑',
    accent: '#d97757', ink: '#b65a3b', accent2: '#4f7cb8', ink2: '#355f96',
  },
  {
    id: 'red', name: '토마토 + 바이올렛', from: 'Todoist 「Add task」 · 날짜 칩 보라',
    accent: '#dc4c3e', ink: '#b8382c', accent2: '#7856d6', ink2: '#5a3db3',
  },
  {
    id: 'green', name: '그린 + 머스터드', from: 'folk 「Deal accepted」 · 노란 아바타',
    accent: '#1f8a5b', ink: '#176b46', accent2: '#d9a400', ink2: '#8a6700',
  },
] as const;

export type AccentId = (typeof ACCENTS)[number]['id'];

const KEY = 'proto-accent';

function loadAccent(): AccentId {
  const raw = localStorage.getItem(KEY);
  return ACCENTS.find((a) => a.id === raw)?.id ?? 'indigo';
}

export function ThemeTuner({ isAdmin, onAdminChange }: { isAdmin: boolean; onAdminChange: (value: boolean) => void }) {
  const [accent, setAccent] = useState<AccentId>(loadAccent);
  const [open, setOpen] = useState(true);
  const current = ACCENTS.find((a) => a.id === accent)!;

  useEffect(() => {
    const root = document.documentElement;
    root.style.setProperty('--accent', current.accent);
    root.style.setProperty('--accent-ink', current.ink);
    root.style.setProperty('--accent2', current.accent2);
    root.style.setProperty('--accent2-ink', current.ink2);
    localStorage.setItem(KEY, accent);
  }, [current, accent]);

  // 숫자 1~5로 후보를 바꾼다. 글을 쓰는 중에는 가로채지 않는다.
  useEffect(() => {
    const onKey = (ev: KeyboardEvent) => {
      const target = ev.target as HTMLElement;
      if (target.closest('input, textarea, [contenteditable]') || ev.ctrlKey || ev.metaKey || ev.altKey) return;
      const index = Number(ev.key) - 1;
      if (index >= 0 && index < ACCENTS.length) setAccent(ACCENTS[index].id);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  return (
    <div className="tuner">
      {open ? (
        <div className="tuner-panel" role="dialog" aria-label="색 조합 후보">
          <div className="tuner-head">
            <strong>색 조합 후보</strong>
            <small>프로토타입 전용 도구</small>
          </div>
          <div className="tuner-list">
            {ACCENTS.map((a, i) => (
              <button key={a.id} className="tuner-option" aria-pressed={a.id === accent} onClick={() => setAccent(a.id)}>
                <span className="tuner-swatch">
                  <span style={{ background: a.accent }} />
                  <span style={{ background: a.accent2 }} />
                </span>
                <span className="tuner-text">
                  <b>{i + 1}. {a.name}</b>
                  <small>{a.from}</small>
                </span>
                <span className="tuner-hex">{a.accent}<br />{a.accent2}</span>
              </button>
            ))}
          </div>
          <dl className="tuner-roles">
            <div><dt><i style={{ background: current.accent }} />메인</dt><dd>지금·복습·주요 버튼</dd></div>
            <div><dt><i style={{ background: current.accent2 }} />두 번째</dt><dd>예습</dd></div>
            <div><dt><i style={{ background: '#1f1f1f' }} />검정</dt><dd>시험</dd></div>
          </dl>
          <div className="tuner-section">
            <span>보는 사람</span>
            <div className="segmented" role="group" aria-label="보는 사람">
              <button aria-pressed={!isAdmin} onClick={() => onAdminChange(false)}>학생</button>
              <button aria-pressed={isAdmin} onClick={() => onAdminChange(true)}>관리자</button>
            </div>
          </div>
          <p className="tuner-keys">단축키: 1–5</p>
        </div>
      ) : null}
      <button className="tuner-toggle" onClick={() => setOpen((v) => !v)} aria-expanded={open}>
        <span className="tuner-dot" />
        {current.name} {open ? '닫기' : ''}
      </button>
    </div>
  );
}
