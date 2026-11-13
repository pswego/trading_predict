import type { ButtonHTMLAttributes, ReactNode } from "react";
import { Link } from "react-router-dom";

export function Shell({ children, wide }: { children: ReactNode; wide?: boolean }) {
  return <div className={`mx-auto w-full ${wide ? "max-w-4xl" : "max-w-2xl"} px-4 pb-24 pt-4`}>{children}</div>;
}

export function TopBar({ title, back = "/", right }: { title: string; back?: string; right?: ReactNode }) {
  return (
    <header className="mb-4 flex items-center gap-2">
      <Link to={back} aria-label="뒤로" className="-ml-2 rounded-lg px-2 py-1 text-xl text-muted hover:text-ink">
        ←
      </Link>
      <h1 className="flex-1 text-lg font-bold">{title}</h1>
      {right}
    </header>
  );
}

export function Button({
  variant = "primary",
  className = "",
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "ghost" | "good" }) {
  const styles = {
    primary: "bg-accent text-accent-ink hover:brightness-105",
    good: "bg-good text-white hover:brightness-110",
    ghost: "bg-panel2 text-ink hover:brightness-110 border border-line",
  }[variant];
  return (
    <button
      {...rest}
      className={`rounded-xl px-4 py-3 text-base font-bold transition active:scale-[0.98] disabled:opacity-40 disabled:active:scale-100 ${styles} ${className}`}
    />
  );
}

export function Chip({ on, children, onClick, sub }: { on: boolean; children: ReactNode; onClick: () => void; sub?: string }) {
  return (
    <button
      type="button"
      aria-pressed={on}
      onClick={onClick}
      className={`rounded-full border px-3.5 py-2 text-sm font-semibold transition ${
        on ? "border-accent bg-accent text-accent-ink" : "border-line bg-panel text-ink hover:border-muted"
      }`}
    >
      {children}
      {sub && <span className={`ml-1.5 text-xs font-normal ${on ? "opacity-70" : "text-muted"}`}>{sub}</span>}
    </button>
  );
}

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <section className={`rounded-2xl border border-line bg-panel p-4 ${className}`}>{children}</section>;
}

export function ErrorNote({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <Card className="text-center">
      <p className="text-sm text-muted">{message}</p>
      {onRetry && (
        <Button variant="ghost" className="mt-3" onClick={onRetry}>
          다시 시도
        </Button>
      )}
    </Card>
  );
}

export function Loading({ label = "불러오는 중…" }: { label?: string }) {
  return <p className="py-16 text-center text-sm text-muted">{label}</p>;
}

export const LABEL = {
  market: { KOSPI: "코스피", KOSDAQ: "코스닥" } as Record<string, string>,
  cap: { large: "대형주", mid: "중형주", small: "소형주", micro: "초소형주" } as Record<string, string>,
  interval: { day: "일봉", week: "주봉" } as Record<string, string>,
  difficulty: { easy: "쉬움", normal: "보통", hard: "어려움", auto: "자동" } as Record<string, string>,
  mode: { quick: "빠른 10문제", survival: "서바이벌", daily: "데일리 챌린지", endless: "무한 연습" } as Record<string, string>,
  source: {
    mirror: "실제 모양을 위아래로 뒤집은 것",
    other_stock: "다른 종목의 실제 구간",
    other_stock_volatility_mismatch: "변동성이 다른 종목의 구간",
    same_market_cap_tier: "같은 시장·비슷한 규모 종목의 구간",
    same_stock_other_period: "같은 종목의 다른 시기",
    same_sector: "같은 업종 다른 종목의 구간",
  } as Record<string, string>,
};

export const fmt = (n: number) => n.toLocaleString("ko-KR");
export const pct = (n: number) => `${n > 0 ? "+" : ""}${n.toFixed(1)}%`;
