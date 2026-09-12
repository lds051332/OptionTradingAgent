export type StreamEvent = {
  type: string;
  message: string;
  ticker: string | null;
  data: Record<string, unknown>;
};

export type Defaults = {
  ok: boolean;
  tickers: string[];
  delta: number;
  cash: number;
  shares?: number;
  cost_basis?: number | null;
  language?: string;
  suggested_language?: string | null;
};

export type DeskMode = "put" | "call";

export type ContractQuote = {
  contract_id: string;
  ticker: string;
  expiry: string;
  dte: number;
  strike: number;
  bid: number;
  ask: number;
  mid: number;
  last?: number | null;
  iv: number;
  delta: number;
  open_interest: number;
  volume: number;
  spread_pct: number;
  quote_source?: "nbbo" | "last";
  iv_source?: "chain" | "implied" | "floored";
};

export type SpreadQuote = {
  short: ContractQuote;
  long: ContractQuote;
  width: number;
  max_loss_per_contract: number;
  contracts: number;
};

export type ContractScore = {
  total: number;
  delta: number;
  iv: number;
  premium: number;
  spread: number;
  expected_move: number;
  liquidity: number;
  strike_distance_pct: number;
  premium_yield: number;
  expected_move_pct: number;
  inside_expected_move: boolean;
};

export type IvContext = {
  atm_iv: number | null;
  hv_20: number | null;
  hv_60: number | null;
  hv_120: number | null;
  iv_hv_ratio: number | null;
  regime: "unknown" | "low" | "normal" | "high" | "rich";
  expected_move_pct: number | null;
  expected_move: number | null;
  expected_move_dte: number | null;
};

export type MarketRegime = {
  label: "risk_on" | "neutral" | "caution" | "risk_off";
  vix: number | null;
  vix3m: number | null;
  vix_term: number | null;
  spy: number | null;
  spy_sma20: number | null;
  spy_sma50: number | null;
  spy_hv20: number | null;
  qqq: number | null;
  qqq_sma20: number | null;
  qqq_sma50: number | null;
  qqq_hv20: number | null;
  why: string;
};

export type BucketCandidate = {
  bucket: string;
  target_delta: number;
  csp: ContractQuote;
  spread: SpreadQuote | null;
  csp_contracts: number;
  assignment_cash: number;
  premium_per_contract: number;
  score?: ContractScore | null;
};

export type SoftMacro = {
  name: string;
  event_date: string;
  kind: string;
};

export type CalendarGate = {
  ticker: string;
  hard_skip: boolean;
  hard_reasons: string[];
  earnings_dates: string[];
  fomc_dates: string[];
  soft_macros: SoftMacro[];
  holding_start: string;
  holding_end: string;
};

export type TickerSnapshot = {
  ticker: string;
  spot: number;
  as_of: string;
  fetched_at: string;
  buckets: Record<string, BucketCandidate>;
  calendar: CalendarGate;
  notes: string[];
  mode?: DeskMode;
  shares?: number | null;
  cost_basis?: number | null;
  iv_context?: IvContext | null;
};

export type ScoutedEvent = {
  title: string;
  expected_time: string | null;
  tickers: string[];
  mechanism: string;
  already_priced: boolean;
  action: string;
  sources: string[];
  detail: string;
};

export type SearchHit = {
  title: string;
  url: string;
  snippet: string;
  query: string;
};

export type PayoffPoint = {
  spot: number;
  pnl: number;
};

export type ExpirationPayoff = {
  structure: string;
  spot: number;
  expiry: string;
  dte: number;
  short_strike: number;
  long_strike: number | null;
  breakeven: number;
  credit_per_share: number;
  contracts: number;
  max_profit: number;
  max_loss: number;
  loss_limited: boolean;
  assignment_cash: number | null;
  cost_basis?: number | null;
  pnl_at_spot: number;
  x_min: number;
  x_max: number;
  points: PayoffPoint[];
};

export type TickerDecision = {
  ticker: string;
  action: string;
  structure: string | null;
  delta_bucket: string | null;
  contract_id: string | null;
  assignment_ok: boolean;
  why: string;
  premium_tradeoff: string | null;
  payoff: ExpirationPayoff | null;
};

export type DeskOutput = {
  decisions: TickerDecision[];
  portfolio_note: string;
  used_llm: boolean;
};

export type DeskRun = {
  as_of: string;
  fetched_at: string;
  cash: number;
  snapshots: TickerSnapshot[];
  events: ScoutedEvent[];
  desk: DeskOutput;
  warnings: string[];
  llm_label: string;
  language: string;
  market?: MarketRegime | null;
};

export type StepStatus = "running" | "done" | "error";

export type TimelineStep = {
  id: string;
  type: string;
  status: StepStatus;
  message: string;
  ticker?: string;
  snapshot?: TickerSnapshot;
  calendar?: CalendarGate;
  hits?: SearchHit[];
  events?: ScoutedEvent[];
  desk?: DeskOutput;
  warnings?: string[];
  market?: MarketRegime;
};
