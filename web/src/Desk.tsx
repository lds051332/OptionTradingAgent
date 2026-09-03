import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { startRun } from "./api";
import { BrandLockup } from "./Brand";
import { PayoffChart } from "./PayoffChart";
import { TickerCombobox, normalizeSymbol } from "./TickerCombobox";
import type {
  BucketCandidate,
  CalendarGate,
  Defaults,
  DeskOutput,
  ScoutedEvent,
  SearchHit,
  StreamEvent,
  TimelineStep,
  TickerSnapshot,
} from "./types";

type Props = {
  defaults: Defaults;
  mode: "put" | "call";
  onBack: () => void;
  onLogout: () => void;
};

const COPY = {
  put: {
    title: "卖 Put 决策台",
    hint: "填好标的、Delta 和本金后开始。",
    disclaimer: "不构成投资建议。下单前请核对成交价与被指派所需现金。",
  },
  call: {
    title: "卖 Call 决策台",
    hint: "填好标的、Delta、持股数量和成本价后开始。",
    disclaimer: "不构成投资建议。下单前请核对成交价；被指派即按行权价卖出持股。",
  },
} as const;

function money(value: number): string {
  return value.toLocaleString("en-US", { maximumFractionDigits: 0 });
}

function compactCash(value: number): string {
  if (value >= 1000) return `$${(value / 1000).toFixed(value % 1000 === 0 ? 0 : 1)}k`;
  return `$${money(value)}`;
}

function upsert(steps: TimelineStep[], next: TimelineStep): TimelineStep[] {
  const index = steps.findIndex((step) => step.id === next.id);
  if (index < 0) return [...steps, next];
  const copy = steps.slice();
  copy[index] = { ...copy[index], ...next };
  return copy;
}

function applyEvent(steps: TimelineStep[], event: StreamEvent): TimelineStep[] {
  const ticker = event.ticker ?? undefined;
  switch (event.type) {
    case "screen_started":
      return upsert(steps, {
        id: `screen:${ticker}`,
        type: "screen",
        status: "running",
        message: event.message,
        ticker,
      });
    case "screen_done":
      return upsert(steps, {
        id: `screen:${ticker}`,
        type: "screen",
        status: "done",
        message: event.message,
        ticker,
        snapshot: event.data.snapshot as TickerSnapshot,
      });
    case "screen_error":
      return upsert(steps, {
        id: `screen:${ticker}`,
        type: "screen",
        status: "error",
        message: event.message,
        ticker,
      });
    case "calendar_started":
      return upsert(steps, {
        id: `calendar:${ticker}`,
        type: "calendar",
        status: "running",
        message: event.message,
        ticker,
      });
    case "calendar_done":
      return upsert(steps, {
        id: `calendar:${ticker}`,
        type: "calendar",
        status: "done",
        message: event.message,
        ticker,
        calendar: event.data.calendar as CalendarGate,
      });
    case "scout_search_started":
      return upsert(steps, {
        id: "scout",
        type: "scout",
        status: "running",
        message: event.message,
        hits: [],
      });
    case "scout_hits":
      return upsert(steps, {
        id: "scout",
        type: "scout",
        status: "running",
        message: event.message,
        hits: event.data.hits as SearchHit[],
      });
    case "scout_llm_started":
      return upsert(steps, {
        id: "scout",
        type: "scout",
        status: "running",
        message: event.message,
        hits: steps.find((s) => s.id === "scout")?.hits,
      });
    case "scout_done":
      return upsert(steps, {
        id: "scout",
        type: "scout",
        status: "done",
        message: event.message,
        hits: steps.find((s) => s.id === "scout")?.hits,
        events: event.data.events as ScoutedEvent[],
        warnings: event.data.warnings as string[],
      });
    case "desk_started":
      return upsert(steps, {
        id: "desk",
        type: "desk",
        status: "running",
        message: event.message,
      });
    case "desk_done":
      return upsert(steps, {
        id: "desk",
        type: "desk",
        status: "done",
        message: event.message,
        desk: event.data.desk as DeskOutput,
      });
    case "run_error":
      return upsert(steps, {
        id: "error",
        type: "error",
        status: "error",
        message: event.message,
      });
    default:
      return steps;
  }
}

export function Desk({ defaults, mode, onBack, onLogout }: Props) {
  const copy = COPY[mode];
  const [ticker, setTicker] = useState(defaults.tickers[0] ?? "");
  const [delta, setDelta] = useState(defaults.delta);
  const [cash, setCash] = useState(defaults.cash);
  const [shares, setShares] = useState(defaults.shares || 100);
  const [costBasis, setCostBasis] = useState(defaults.cost_basis || 0);
  const [configOpen, setConfigOpen] = useState(true);
  const [running, setRunning] = useState(false);
  const [steps, setSteps] = useState<TimelineStep[]>([]);
  const [userPrompt, setUserPrompt] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    return () => abortRef.current?.abort();
  }, []);

  function stopRun() {
    abortRef.current?.abort();
    abortRef.current = null;
  }

  const summary = useMemo(() => {
    if (mode === "call") {
      const basis = costBasis > 0 ? `成本 $${costBasis.toFixed(2)}` : "未填成本";
      return `${ticker || "未选标的"} · Δ${delta.toFixed(2)} · ${shares}股 · ${basis}`;
    }
    return `${ticker || "未选标的"} · Δ${delta.toFixed(2)} · ${compactCash(cash)}`;
  }, [mode, ticker, delta, cash, shares, costBasis]);

  const verdict = steps.find((step) => step.id === "desk" && step.status === "done")?.desk;

  async function onAnalyze(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const raw = String(new FormData(event.currentTarget).get("ticker") ?? ticker);
    const symbol = normalizeSymbol(raw);
    if (running || !symbol) return;
    if (mode === "call" && (shares < 100 || costBasis <= 0)) return;
    setTicker(symbol);
    setRunning(true);
    setError(null);
    setSteps([]);
    setConfigOpen(false);
    setUserPrompt(
      mode === "call"
        ? `分析 ${symbol} · Δ ${delta.toFixed(2)} · ${shares}股 · 成本 $${costBasis.toFixed(2)}`
        : `分析 ${symbol} · Δ ${delta.toFixed(2)} · 本金 $${money(cash)}`,
    );
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    try {
      const body =
        mode === "call"
          ? { tickers: [symbol], delta, mode: "call" as const, shares, cost_basis: costBasis }
          : { tickers: [symbol], delta, cash, mode: "put" as const };
      for await (const item of startRun(body, { signal: controller.signal })) {
        setSteps((current) => applyEvent(current, item));
        if (item.type === "run_error") setError(item.message);
      }
    } catch (err) {
      if (controller.signal.aborted || (err instanceof Error && err.name === "AbortError")) {
        return;
      }
      const message = err instanceof Error ? err.message : "分析失败";
      setError(message);
      setSteps((current) =>
        applyEvent(current, { type: "run_error", message, ticker: null, data: {} }),
      );
    } finally {
      if (abortRef.current === controller) abortRef.current = null;
      setRunning(false);
    }
  }

  return (
    <div className="mx-auto flex min-h-dvh max-w-2xl flex-col px-4 pb-[max(1.5rem,env(safe-area-inset-bottom))] pt-[max(1rem,env(safe-area-inset-top))]">
      <header className="mb-4 flex items-center justify-between gap-3">
        <BrandLockup title={copy.title} />
        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={() => {
              stopRun();
              onBack();
            }}
            className="min-h-11 px-2 text-sm text-[var(--mute)]"
          >
            返回
          </button>
          <button
            type="button"
            onClick={() => {
              stopRun();
              onLogout();
            }}
            className="min-h-11 px-2 text-sm text-[var(--mute)]"
          >
            退出
          </button>
        </div>
      </header>

      <section className="ticket mb-5 px-4 py-3 pl-7">
        <button
          type="button"
          className="flex min-h-11 w-full items-center justify-between gap-3 text-left"
          onClick={() => setConfigOpen((open) => !open)}
        >
          <span className="font-[family-name:var(--font-mono)] text-sm text-[var(--chalk)]">
            {summary}
          </span>
          <span className="text-xs text-[var(--mute)]">{configOpen ? "收起" : "改参数"}</span>
        </button>
        {configOpen ? (
          <form onSubmit={onAnalyze} className="mt-3 border-t border-[var(--hairline)] pt-4">
            <label htmlFor="ticker" className="text-xs tracking-wide text-[var(--mute)] uppercase">
              标的
            </label>
            <TickerCombobox id="ticker" value={ticker} onChange={setTicker} />
            <div className="mt-4 grid grid-cols-2 gap-3">
              <label className="block">
                <span className="text-xs tracking-wide text-[var(--mute)] uppercase">Delta 锚</span>
                <input
                  type="number"
                  step="0.01"
                  min={0.05}
                  max={0.25}
                  value={delta}
                  onChange={(e) => setDelta(Number(e.target.value))}
                  className="mt-2 min-h-11 w-full rounded-sm border border-[var(--hairline)] bg-[var(--night)] px-3 font-[family-name:var(--font-mono)]"
                />
              </label>
              {mode === "call" ? (
                <label className="block">
                  <span className="text-xs tracking-wide text-[var(--mute)] uppercase">持股数量</span>
                  <input
                    type="number"
                    min={100}
                    step={1}
                    value={shares}
                    onChange={(e) => setShares(Number(e.target.value))}
                    className="mt-2 min-h-11 w-full rounded-sm border border-[var(--hairline)] bg-[var(--night)] px-3 font-[family-name:var(--font-mono)]"
                  />
                </label>
              ) : (
                <label className="block">
                  <span className="text-xs tracking-wide text-[var(--mute)] uppercase">本金 USD</span>
                  <input
                    type="number"
                    min={1000}
                    step={1000}
                    value={cash}
                    onChange={(e) => setCash(Number(e.target.value))}
                    className="mt-2 min-h-11 w-full rounded-sm border border-[var(--hairline)] bg-[var(--night)] px-3 font-[family-name:var(--font-mono)]"
                  />
                </label>
              )}
            </div>
            {mode === "call" ? (
              <label className="mt-3 block">
                <span className="text-xs tracking-wide text-[var(--mute)] uppercase">成本价 USD</span>
                <input
                  type="number"
                  min={0.01}
                  step={0.01}
                  value={costBasis || ""}
                  onChange={(e) => setCostBasis(Number(e.target.value))}
                  placeholder="买入均价"
                  className="mt-2 min-h-11 w-full rounded-sm border border-[var(--hairline)] bg-[var(--night)] px-3 font-[family-name:var(--font-mono)]"
                />
              </label>
            ) : null}
            <button
              type="submit"
              disabled={running || !ticker || (mode === "call" && (shares < 100 || costBasis <= 0))}
              className="mt-4 min-h-11 w-full rounded-sm bg-[var(--brass)] font-semibold text-[var(--night)] disabled:opacity-50"
            >
              {running ? "分析进行中…" : "开始分析"}
            </button>
          </form>
        ) : null}
      </section>

      <div className="flex flex-1 flex-col gap-4">
        {userPrompt ? (
          <div className="ml-8 self-end rounded-2xl rounded-br-sm bg-[var(--brass)]/15 px-4 py-3 text-sm text-[var(--chalk)]">
            {userPrompt}
          </div>
        ) : (
          <p className="px-1 text-sm leading-relaxed text-[var(--mute)]">
            {copy.hint}
          </p>
        )}

        {steps.map((step) => (
          <StepCard key={step.id} step={step} mode={mode} />
        ))}

        {error && !steps.some((step) => step.type === "error") ? (
          <p className="text-sm text-[var(--skip)]">{error}</p>
        ) : null}

        {verdict ? <VerdictCard desk={verdict} mode={mode} /> : null}
      </div>
    </div>
  );
}

function StatusMark({ status }: { status: TimelineStep["status"] }) {
  if (status === "running") return <span className="pulse-dot" aria-hidden />;
  if (status === "error") return <span className="text-[var(--skip)]">×</span>;
  return <span className="text-[var(--brass)]">✓</span>;
}

function WorkingReel({ label }: { label: string }) {
  return (
    <div className="work-reel mt-3" aria-live="polite">
      <p className="work-reel-label">
        {label}
        <span className="work-ellipsis" />
      </p>
      <div className="work-reel-track" />
      <div className="work-skel">
        <span />
        <span />
        <span />
      </div>
    </div>
  );
}

function StepCard({ step, mode }: { step: TimelineStep; mode: "put" | "call" }) {
  const live = step.status === "running";
  return (
    <article className={`ticket px-4 py-4 pl-7 ${live ? "ticket-live" : ""}`}>
      <header className="mb-2 flex items-center gap-2">
        <StatusMark status={step.status} />
        <h2 className="font-[family-name:var(--font-display)] text-lg">{stepTitle(step)}</h2>
        {live ? (
          <span className="ml-auto font-[family-name:var(--font-mono)] text-[11px] tracking-[0.18em] text-[var(--brass)] uppercase">
            工作中
          </span>
        ) : null}
      </header>
      {live ? <WorkingReel label={step.message} /> : <p className="text-sm text-[var(--mute)]">{step.message}</p>}
      {step.snapshot ? <Buckets snapshot={step.snapshot} mode={mode} /> : null}
      {!live && step.calendar ? <CalendarBlock calendar={step.calendar} /> : null}
      {step.hits && step.hits.length > 0 ? <Hits hits={step.hits} /> : null}
      {!live && step.events ? <Events events={step.events} /> : null}
      {step.warnings?.length ? (
        <ul className="mt-2 list-disc pl-4 text-xs text-[var(--skip)]">
          {step.warnings.map((warning) => (
            <li key={warning}>{warning}</li>
          ))}
        </ul>
      ) : null}
    </article>
  );
}

function stepTitle(step: TimelineStep): string {
  if (step.type === "screen") return `筛链 ${step.ticker ?? ""}`.trim();
  if (step.type === "calendar") return `日历 ${step.ticker ?? ""}`.trim();
  if (step.type === "scout") return "事件侦察";
  if (step.type === "desk") return "终审";
  if (step.type === "error") return "中断";
  return step.type;
}

function Buckets({ snapshot, mode }: { snapshot: TickerSnapshot; mode: "put" | "call" }) {
  const buckets = Object.values(snapshot.buckets);
  const call = mode === "call";
  const lastPrint = buckets.some((bucket) => bucket.csp.quote_source === "last");
  const ivNote = buckets.some((bucket) => bucket.csp.iv_source === "implied" || bucket.csp.iv_source === "floored");
  const otherNotes = (snapshot.notes ?? []).filter(
    (note) => !note.includes("过期成交价") && !note.includes("Last print") && !note.includes("链上 IV") && !note.includes("Chain IV"),
  );
  return (
    <div className="mt-3 overflow-x-auto">
      <p className="font-[family-name:var(--font-mono)] text-xs text-[var(--brass)]">
        {snapshot.ticker} 现价 {snapshot.spot.toFixed(2)} · 候选档位
      </p>
      {lastPrint ? (
        <div className="tape-delay">
          <p className="tape-delay-kicker">Last print · 非盘口</p>
          <p>
            买卖价为空，权利金用最新成交价，价差未知。Yahoo 盘后常见。下单前必须核实现价与买卖盘。
          </p>
          {ivNote ? (
            <p>链上 IV 不可用，Δ 由成交价反推（失败则套下限），只用于选档，不是交易所 Greek。</p>
          ) : null}
        </div>
      ) : null}
      {otherNotes.length ? (
        <ul className="mt-1 text-[11px] text-[var(--mute)]">
          {otherNotes.map((note) => (
            <li key={note}>{note}</li>
          ))}
        </ul>
      ) : null}
      {buckets.length === 0 ? (
        <p className="mt-2 text-sm text-[var(--mute)]">{call ? "两档都没有合格 call。" : "两档都没有合格合约。"}</p>
      ) : (
        <table className="mt-2 w-full min-w-[28rem] text-left text-xs">
          <thead className="text-[var(--mute)]">
            <tr>
              <th className="py-1 font-medium">档位</th>
              <th className="py-1 font-medium">合约</th>
              <th className="py-1 font-medium">Δ</th>
              <th className="py-1 font-medium">权利金</th>
              <th className="py-1 font-medium">{call ? "CC" : "CSP"}</th>
            </tr>
          </thead>
          <tbody className="font-[family-name:var(--font-mono)]">
            {buckets.map((bucket) => (
              <BucketRow key={bucket.bucket} bucket={bucket} call={call} />
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

function BucketRow({ bucket, call }: { bucket: BucketCandidate; call: boolean }) {
  const spread = bucket.spread
    ? `价差 ${bucket.spread.long.strike} / ${bucket.spread.contracts}张`
    : "无价差";
  const last = bucket.csp.quote_source === "last";
  const ivMark =
    bucket.csp.iv_source === "implied" ? "Δ反推" : bucket.csp.iv_source === "floored" ? "IV下限" : null;
  return (
    <tr className="border-t border-[var(--hairline)]">
      <td className="py-2">{bucket.bucket}</td>
      <td className="py-2">{bucket.csp.contract_id}</td>
      <td className="py-2">
        {bucket.csp.delta.toFixed(3)}
        {ivMark ? <span className="quote-mark">{ivMark}</span> : null}
      </td>
      <td className="py-2">
        ${money(bucket.premium_per_contract)}
        {last ? <span className="quote-mark">成交价</span> : null}
      </td>
      <td className="py-2">
        {call ? (
          <>
            {bucket.csp_contracts}张
            <div className="text-[10px] text-[var(--mute)]">行权价卖出 ${money(bucket.assignment_cash)}</div>
          </>
        ) : (
          <>
            {bucket.csp_contracts}张 · ${money(bucket.assignment_cash)}
            <div className="text-[10px] text-[var(--mute)]">{spread}</div>
          </>
        )}
      </td>
    </tr>
  );
}

function CalendarBlock({ calendar }: { calendar: CalendarGate }) {
  return (
    <div className="mt-3 text-sm">
      <p>
        持有窗口 {calendar.holding_start} → {calendar.holding_end}
      </p>
      {calendar.hard_skip ? (
        <p className="mt-1 text-[var(--skip)]">{calendar.hard_reasons.join("；") || "硬性跳过"}</p>
      ) : calendar.soft_macros.length ? (
        <p className="mt-1 text-[var(--brass)]">
          软宏观{" "}
          {calendar.soft_macros.map((item) => `${item.kind} ${item.event_date}`).join(" · ")}
        </p>
      ) : (
        <p className="mt-1 text-[var(--mute)]">无硬日历冲突</p>
      )}
    </div>
  );
}

function Hits({ hits }: { hits: SearchHit[] }) {
  const latest = hits.slice(-6);
  return (
    <ul className="mt-3 space-y-2 text-sm">
      {latest.map((hit) => (
        <li key={`${hit.url}-${hit.title}`}>
          <a href={hit.url} target="_blank" rel="noreferrer" className="text-[var(--chalk)] underline-offset-2 hover:underline">
            {hit.title || hit.url}
          </a>
          <p className="line-clamp-2 text-xs text-[var(--mute)]">{hit.snippet}</p>
        </li>
      ))}
    </ul>
  );
}

function Events({ events }: { events: ScoutedEvent[] }) {
  if (events.length === 0) {
    return <p className="mt-3 text-sm text-[var(--mute)]">没有需要跟进的日历外事件。</p>;
  }
  return (
    <ul className="mt-3 space-y-2">
      {events.map((event) => (
        <li key={`${event.title}-${event.expected_time}`} className="text-sm">
          <span className="font-[family-name:var(--font-mono)] text-xs text-[var(--brass)]">
            {event.action} / {event.mechanism}
          </span>
          <p>{event.title}</p>
          <p className="text-xs text-[var(--mute)]">{event.expected_time || "无日期"}</p>
        </li>
      ))}
    </ul>
  );
}

function structureLabel(structure: string | null): string {
  if (structure === "BULL_PUT_SPREAD") return "牛市看跌价差";
  if (structure === "COVERED_CALL") return "Covered Call";
  if (structure === "CSP") return "CSP";
  return structure ?? "";
}

function VerdictCard({ desk, mode }: { desk: DeskOutput; mode: "put" | "call" }) {
  const copy = COPY[mode];
  return (
    <section className="ticket px-4 py-5 pl-7">
      <p className="font-[family-name:var(--font-mono)] text-[11px] tracking-[0.22em] text-[var(--brass)] uppercase">
        终审盖章
      </p>
      <div className="mt-4 flex flex-col gap-5">
        {desk.decisions.map((decision) => (
          <div key={decision.ticker}>
            <div className="flex items-start justify-between gap-4">
              <div className="min-w-0">
                <p className="font-[family-name:var(--font-mono)] text-sm text-[var(--mute)]">
                  {decision.ticker}
                  {decision.structure ? ` · ${structureLabel(decision.structure)}` : ""}
                  {decision.delta_bucket ? ` · ${decision.delta_bucket}` : ""}
                </p>
                {decision.contract_id ? (
                  <p className="mt-1 break-all font-[family-name:var(--font-mono)] text-sm">
                    {decision.contract_id}
                  </p>
                ) : null}
                <p className="mt-2 text-sm leading-relaxed text-[var(--chalk)]">{decision.why}</p>
                {decision.premium_tradeoff ? (
                  <p className="mt-1 text-xs text-[var(--mute)]">{decision.premium_tradeoff}</p>
                ) : null}
              </div>
              <span className={`stamp shrink-0 ${decision.action === "OPEN" ? "stamp-open" : "stamp-skip"}`}>
                {decision.action}
              </span>
            </div>
            {decision.action === "OPEN" && decision.payoff ? (
              <PayoffChart ticker={decision.ticker} payoff={decision.payoff} />
            ) : null}
          </div>
        ))}
      </div>
      {desk.portfolio_note ? (
        <p className="mt-4 border-t border-[var(--hairline)] pt-3 text-sm text-[var(--mute)]">
          {desk.portfolio_note}
        </p>
      ) : null}
      <p className="mt-3 text-xs text-[var(--mute)]">{copy.disclaimer}</p>
    </section>
  );
}
