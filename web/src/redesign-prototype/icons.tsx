import type { ReactNode } from 'react';

/** 선 아이콘. 1.6px 선, 24 격자. 외부 아이콘 패키지 없이 쓴다. */
function Svg({ children, size = 18 }: { children: ReactNode; size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.6}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {children}
    </svg>
  );
}

export const Icon = {
  calendar: () => (
    <Svg>
      <rect x="3" y="4.5" width="18" height="16.5" rx="2.5" />
      <path d="M16 2.5v4M8 2.5v4M3 10h18" />
    </Svg>
  ),
  layers: () => (
    <Svg>
      <path d="m12 3 9 4.5-9 4.5-9-4.5z" />
      <path d="m3 12 9 4.5 9-4.5" />
      <path d="m3 16.5 9 4.5 9-4.5" />
    </Svg>
  ),
  target: () => (
    <Svg>
      <circle cx="12" cy="12" r="9" />
      <circle cx="12" cy="12" r="5" />
      <circle cx="12" cy="12" r="1.2" />
    </Svg>
  ),
  chart: () => (
    <Svg>
      <path d="M4 20V10M10 20V4M16 20v-7M22 20H2" />
    </Svg>
  ),
  bookmark: () => (
    <Svg>
      <path d="M6 3.5h12v17l-6-4-6 4z" />
    </Svg>
  ),
  message: () => (
    <Svg>
      <path d="M7.9 20A9 9 0 1 0 4 16.1L2.5 21.5Z" />
    </Svg>
  ),
  users: () => (
    <Svg>
      <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" />
      <circle cx="9" cy="7" r="4" />
      <path d="M22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75" />
    </Svg>
  ),
  bell: () => (
    <Svg>
      <path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9" />
      <path d="M10.3 21a1.94 1.94 0 0 0 3.4 0" />
    </Svg>
  ),
  help: () => (
    <Svg>
      <circle cx="12" cy="12" r="9" />
      <path d="M9.1 9a3 3 0 0 1 5.8 1c0 2-3 3-3 3M12 17h.01" />
    </Svg>
  ),
  shield: () => (
    <Svg>
      <path d="M12 21.5s8-4 8-10v-6l-8-3-8 3v6c0 6 8 10 8 10z" />
    </Svg>
  ),
  card: () => (
    <Svg>
      <rect x="2.5" y="5" width="19" height="14" rx="2.5" />
      <path d="M2.5 10h19" />
    </Svg>
  ),
  settings: () => (
    <Svg>
      <path d="M4 21v-7M4 10V3M12 21v-9M12 8V3M20 21v-5M20 12V3M1.5 14h5M9.5 8h5M17.5 16h5" />
    </Svg>
  ),
  panel: () => (
    <Svg>
      <rect x="3" y="3.5" width="18" height="17" rx="2.5" />
      <path d="M9 3.5v17" />
    </Svg>
  ),
  search: () => (
    <Svg>
      <circle cx="11" cy="11" r="7" />
      <path d="m20.5 20.5-4.5-4.5" />
    </Svg>
  ),
  upDown: () => (
    <Svg size={16}>
      <path d="m7 15 5 5 5-5M7 9l5-5 5 5" />
    </Svg>
  ),
  left: () => (
    <Svg>
      <path d="m15 18-6-6 6-6" />
    </Svg>
  ),
  right: () => (
    <Svg>
      <path d="m9 18 6-6-6-6" />
    </Svg>
  ),
  x: () => (
    <Svg>
      <path d="M18 6 6 18M6 6l12 12" />
    </Svg>
  ),
  external: () => (
    <Svg size={16}>
      <path d="M7 17 17 7M8 7h9v9" />
    </Svg>
  ),
  download: () => (
    <Svg size={16}>
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3" />
    </Svg>
  ),
  play: () => (
    <Svg size={16}>
      <path d="M7 4.5v15l12-7.5z" />
    </Svg>
  ),
  flag: () => (
    <Svg size={16}>
      <path d="M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1zM4 22v-7" />
    </Svg>
  ),
  file: () => (
    <Svg size={16}>
      <path d="M14 2.5H6a2 2 0 0 0-2 2v15a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8.5z" />
      <path d="M14 2.5v6h6M8 13h8M8 17h5" />
    </Svg>
  ),
  logout: () => (
    <Svg size={16}>
      <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9" />
    </Svg>
  ),
  mail: () => (
    <Svg>
      <rect x="2.5" y="4.5" width="19" height="15" rx="2.5" />
      <path d="m3 6.5 9 6.5 9-6.5" />
    </Svg>
  ),
  list: () => (
    <Svg>
      <path d="M9 6h11M9 12h11M9 18h11" />
      <circle cx="4.5" cy="6" r="1" />
      <circle cx="4.5" cy="12" r="1" />
      <circle cx="4.5" cy="18" r="1" />
    </Svg>
  ),
  note: () => (
    <Svg>
      <path d="M12 3.5H6a2.5 2.5 0 0 0-2.5 2.5v12A2.5 2.5 0 0 0 6 20.5h12a2.5 2.5 0 0 0 2.5-2.5v-6" />
      <path d="M18.4 2.6a2 2 0 0 1 2.9 2.9L12.5 14.3 9 15l.7-3.5z" />
    </Svg>
  ),
  check: () => (
    <Svg size={14}>
      <path d="m5 12.5 4.5 4.5L19 7.5" />
    </Svg>
  ),
  chevronDown: () => (
    <Svg size={16}>
      <path d="m6 9 6 6 6-6" />
    </Svg>
  ),
  minus: () => (
    <Svg size={14}>
      <path d="M5 12h14" />
    </Svg>
  ),
  pencil: () => (
    <Svg size={15}>
      <path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L8 18l-4 1 1-4z" />
    </Svg>
  ),
  plus: () => (
    <Svg size={16}>
      <path d="M12 5v14M5 12h14" />
    </Svg>
  ),
};
