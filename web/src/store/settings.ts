import { create } from "zustand";

type Theme = "system" | "dark" | "light";
type Colors = "kr" | "us";

interface Settings {
  theme: Theme;
  colors: Colors;
  sound: boolean;
  set: (patch: Partial<Pick<Settings, "theme" | "colors" | "sound">>) => void;
}

const KEY = "chartgap.settings";

function load(): Partial<Settings> {
  try {
    return JSON.parse(localStorage.getItem(KEY) ?? "{}");
  } catch {
    return {};
  }
}

function apply(s: Pick<Settings, "theme" | "colors">) {
  const el = document.documentElement;
  if (s.theme === "system") el.removeAttribute("data-theme");
  else el.setAttribute("data-theme", s.theme);
  el.setAttribute("data-colors", s.colors);
}

export const useSettings = create<Settings>((set, get) => {
  const saved = load();
  const init = { theme: saved.theme ?? "system", colors: saved.colors ?? "kr", sound: saved.sound ?? false } as const;
  apply(init);
  return {
    ...init,
    set: (patch) => {
      set(patch);
      const { theme, colors, sound } = get();
      apply({ theme, colors });
      try {
        localStorage.setItem(KEY, JSON.stringify({ theme, colors, sound }));
      } catch {
        /* 저장 못 해도 동작에는 지장 없음 */
      }
    },
  };
});

let ctx: AudioContext | null = null;

export function beep(kind: "good" | "bad" | "tick") {
  if (!useSettings.getState().sound) return;
  try {
    ctx ??= new AudioContext();
    const notes = kind === "good" ? [660, 880] : kind === "bad" ? [220, 165] : [520];
    notes.forEach((f, i) => {
      const o = ctx!.createOscillator();
      const g = ctx!.createGain();
      o.type = kind === "bad" ? "sawtooth" : "sine";
      o.frequency.value = f;
      const t = ctx!.currentTime + i * 0.09;
      g.gain.setValueAtTime(0.08, t);
      g.gain.exponentialRampToValueAtTime(0.001, t + 0.14);
      o.connect(g).connect(ctx!.destination);
      o.start(t);
      o.stop(t + 0.15);
    });
  } catch {
    /* 오디오를 쓸 수 없는 환경 */
  }
}
