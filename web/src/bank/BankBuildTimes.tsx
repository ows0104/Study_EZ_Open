import type { BankTimeline } from "../types/bank";

const koreanTime = new Intl.DateTimeFormat("ko-KR", {
  timeZone: "Asia/Seoul", year: "numeric", month: "2-digit", day: "2-digit",
  hour: "2-digit", minute: "2-digit", second: "2-digit", hourCycle: "h23",
});

export function BankBuildTimes({ timeline }: { timeline?: BankTimeline | null }) {
  const times = [["퀴즈 링크 생성", timeline?.linkedAt], ["최종퀴즈 업로드", timeline?.builtAt]] as const;
  return <>{times.map(([label, value]) => value && Number.isFinite(Date.parse(value))
    ? <small key={label} title={label === "퀴즈 링크 생성" ? "공유 링크가 서버에 처음 저장되거나 새 링크로 바뀐 시각" : "최종퀴즈 결과가 서버에 업로드되어 저장된 시각"}>{label} <time dateTime={value}>{koreanTime.format(new Date(value))}</time> (한국 시간)</small>
    : null)}</>;
}
