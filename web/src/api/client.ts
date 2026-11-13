import type { Layout, OHLC } from "../chart/scale";

export type Mode = "quick" | "survival" | "daily" | "endless";
export type GameType = "choice4" | "ox";
export type Difficulty = "easy" | "normal" | "hard";

export interface Filters {
  interval: "day" | "week";
  markets: string[];
  cap_tiers: string[];
  eras: string[];
}
export interface SessionRequest {
  mode: Exclude<Mode, "daily">;
  game_type: GameType;
  filters: Filters;
  difficulty: Difficulty | "auto";
}
export interface GameState {
  session_id: string;
  mode: Mode;
  game_type: GameType;
  score: number;
  streak: number;
  lives: number | null;
  answered: number;
  correct: number;
  total: number | null;
  finished: boolean;
}
export interface Question {
  play_token: string;
  index: number;
  total: number | null;
  game_type: GameType;
  difficulty: Difficulty;
  time_limit_ms: number | null;
  remaining_ms: number | null;
  layout: Layout;
  candles: OHLC[];
  volume: number[] | null;
  ma: Record<string, (number | null)[]> | null;
  context_hint: { market: string; cap_tier: string; interval: string };
  state: GameState;
  widened: boolean;
  options?: OHLC[][];
  option_volume?: number[][] | null;
  candidate?: OHLC[];
  candidate_volume?: number[] | null;
}
export interface Finished {
  finished: true;
  state: GameState;
  empty?: boolean;
}
export interface Reveal {
  name: string;
  code: string;
  market: string;
  start_date: string;
  gap_start: string;
  gap_end: string;
  end_date: string;
  cap_tier_then: string;
  gap_return_pct: number;
  gap_max_pct: number;
  gap_min_pct: number;
  delisted: { date: string; reason: string } | null;
  decoy_sources: string[];
}
export interface AnswerResult {
  correct: boolean;
  timed_out: boolean;
  score_delta: number;
  state: GameState;
  elo: { before: number; after: number };
  reveal: Reveal;
  correct_choice?: number;
  decoy_sources?: (string | null)[];
  shown_was_real?: boolean;
  real?: OHLC[];
  real_volume?: number[] | null;
}
export interface Summary extends GameState {
  plays: { correct: boolean; score: number; difficulty: Difficulty; name: string; code: string; gap_start: string; gap_end: string; gap_return_pct: number }[];
  share_text: string;
  elo: number;
  best_streak: number;
  daily_date: string | null;
}
export interface Option {
  value: string;
  label: string;
  count: number;
}
export interface Meta {
  intervals: { value: "day" | "week"; label: string }[];
  by_interval: Record<string, { total: number; markets: Option[]; cap_tiers: Option[]; eras: Option[]; difficulties: Option[] }>;
  quick_total: number;
  survival_lives: number;
}
export interface PoolCount {
  total: number;
  remaining: number;
  low: boolean;
}
export interface DailyStatus {
  date: string;
  available: boolean;
  session: GameState | null;
}
export interface Leaderboard {
  date: string;
  top: { rank: number; nickname: string; score: number; correct: number; duration_ms: number; me: boolean }[];
  my_rank: number | null;
  players: number;
}
export interface Stat {
  key: string;
  plays: number;
  correct: number;
}
export interface Stats {
  nickname: string | null;
  elo: number;
  best_streak: number;
  plays: number;
  correct: number;
  score: number;
  by_difficulty: Stat[];
  by_market: Stat[];
  by_cap_tier: Stat[];
  by_interval: Stat[];
}

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

async function call<T>(path: string, body?: unknown): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`/api${path}`, {
      method: body === undefined ? "GET" : "POST",
      headers: body === undefined ? undefined : { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
      credentials: "same-origin",
    });
  } catch {
    throw new ApiError(0, "서버에 연결할 수 없어요. 네트워크를 확인하고 다시 시도해 주세요.");
  }
  if (!res.ok) {
    let msg = "문제가 생겼어요. 잠시 후 다시 시도해 주세요.";
    try {
      const j = await res.json();
      if (typeof j.detail === "string") msg = j.detail;
    } catch {
      /* 본문이 JSON이 아님 */
    }
    throw new ApiError(res.status, msg);
  }
  return res.json() as Promise<T>;
}

export const api = {
  health: () => call<{ ok: boolean; questions: number }>("/health"),
  meta: () => call<Meta>("/meta/filters"),
  poolCount: (req: SessionRequest) => call<PoolCount>("/pool/count", req),
  createSession: (req: SessionRequest) => call<GameState>("/sessions", req),
  next: (sid: string) => call<Question | Finished>(`/sessions/${sid}/next`),
  answer: (play_token: string, choice: number | "O" | "X" | null) => call<AnswerResult>("/answer", { play_token, choice }),
  summary: (sid: string) => call<Summary>(`/sessions/${sid}/summary`),
  daily: () => call<DailyStatus>("/daily"),
  dailyStart: () => call<GameState>("/daily/start", {}),
  leaderboard: (date?: string) => call<Leaderboard>(`/daily/leaderboard${date ? `?date=${date}` : ""}`),
  setNickname: (nickname: string) => call<{ nickname: string }>("/me/nickname", { nickname }),
  stats: () => call<Stats>("/me/stats"),
};
