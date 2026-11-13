import { useEffect, useRef, useState } from "react";

/** 남은 시간 막대. 시간이 다 되면 onExpire를 한 번 부른다. */
export default function Timer({ totalMs, remainingMs, running, onExpire }: { totalMs: number; remainingMs: number; running: boolean; onExpire: () => void }) {
  const [left, setLeft] = useState(remainingMs);
  const expire = useRef(onExpire);
  expire.current = onExpire;

  useEffect(() => {
    if (!running) return;
    const deadline = performance.now() + remainingMs;
    let raf = 0;
    let done = false;
    const tick = () => {
      const l = Math.max(deadline - performance.now(), 0);
      setLeft(l);
      if (l <= 0) {
        if (!done) {
          done = true;
          expire.current();
        }
        return;
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [running, remainingMs]);

  const frac = Math.max(Math.min(left / totalMs, 1), 0);
  const urgent = left < 5000;
  return (
    <div className="flex items-center gap-2" role="timer" aria-label={`남은 시간 ${Math.ceil(left / 1000)}초`}>
      <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-panel2">
        <div className={`h-full rounded-full ${urgent ? "bg-bad" : "bg-accent"}`} style={{ width: `${frac * 100}%` }} />
      </div>
      <span className={`w-7 text-right text-xs tnum ${urgent ? "font-bold text-bad" : "text-muted"}`}>{Math.ceil(left / 1000)}</span>
    </div>
  );
}
