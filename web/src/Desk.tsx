import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { startRun } from "./api";
import { BrandLockup } from "./Brand";
import { Link } from "./router";
import { PayoffChart } from "./PayoffChart";
import { TickerCombobox, normalizeSymbol } from "./TickerCombobox";
import { dateLocale, type MsgKey } from "./i18n";
import { LangSwitch, useI18n } from "./locale";
import { formatCachedAt, loadCachedRun, saveCachedRun } from "./runCache";
import type {
  BucketCandidate,
  CalendarGate,
  Defaults,
  DeskOutput,
  MarketRegime,
  ScoutedEvent,
  SearchHit,
  StreamEvent,
  TimelineStep,
  TickerSnapshot,
} from "./types";
import { QualityPanel, RegimeBlock } from "./QualityPanel";

type Props = {
  defaults: Defaults;
  mode: "put" | "call";
};

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
    case "regime_started":
      return upsert(steps, {
        id: "regime",
        type: "regime",
        status: "running",
        message: event.message,
      });
    case "regime_done":
      return upsert(steps, {
        id: "regime",
        type: "regime",
        status: "done",
        message: event.message,
        market: event.data.market as MarketRegime | undefined,
      });
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

export function Desk({ defaults, mode }: Props) {
  const { lang, t } = useI18n();
  const title = mode === "call" ? t("desk.callTitle") : t("desk.putTitle");
  const hint = mode === "call" ? t("desk.callHint") : t("desk.putHint");
  const [seed] = useState(() => loadCachedRun(mode, lang));
  const [ticker, setTicker] = useState(seed?.ticker || defaults.tickers[0] || "");
  const [delta, setDelta] = useState(seed?.delta ?? defaults.delta);
  const [cash, setCash] = useState(seed?.cash ?? defaults.cash);
  const [shares, setShares] = useState(seed?.shares || defaults.shares || 100);
  const [costBasis, setCostBasis] = useState(seed?.costBasis || defaults.cost_basis || 0);
  const [configOpen, setConfigOpen] = useState(!seed);
  const [running, setRunning] = useState(false);
  const [steps, setSteps] = useState<TimelineStep[]>(seed?.steps ?? []);
  const [userPrompt, setUserPrompt] = useState<string | null>(seed?.userPrompt ?? null);
  const [error, setError] = useState<string | null>(seed?.error ?? null);
  const [cachedAt, setCachedAt] = useState<string | null>(seed?.savedAt ?? null);
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
      const basis = costBasis > 0 ? t("desk.costPrefix", { value: costBasis.toFixed(2) }) : t("desk.noCost");
      return `${ticker || t("desk.noTicker")} · Δ${delta.toFixed(2)} · ${t("desk.sharesPart", { n: shares })} · ${basis}`;
    }
    return `${ticker || t("desk.noTicker")} · Δ${delta.toFixed(2)} · ${compactCash(cash)}`;
  }, [mode, ticker, delta, cash, shares, costBasis, t]);

  const verdict = steps.find((step) => step.id === "desk" && step.status === "done")?.desk;
  const hasResult = steps.length > 0 || Boolean(userPrompt);

  async function onAnalyze(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const raw = String(new FormData(event.currentTarget).get("ticker") ?? ticker);
    await runAnalysis(raw);
  }

  async function runAnalysis(rawTicker: string) {
    const symbol = normalizeSymbol(rawTicker);
    if (running || !symbol) return;
    if (mode === "call" && (shares < 100 || costBasis <= 0)) return;
    setTicker(symbol);
    setRunning(true);
    setError(null);
    setSteps([]);
    setCachedAt(null);
    setConfigOpen(false);
    const prompt =
      mode === "call"
        ? t("desk.promptCall", {
            symbol,
            delta: delta.toFixed(2),
            shares,
            cost: costBasis.toFixed(2),
          })
        : t("desk.promptPut", { symbol, delta: delta.toFixed(2), cash: money(cash) });
    setUserPrompt(prompt);
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    let latest: TimelineStep[] = [];
    let latestError: string | null = null;
    let aborted = false;
    try {
      const body =
        mode === "call"
          ? { tickers: [symbol], delta, mode: "call" as const, shares, cost_basis: costBasis }
          : { tickers: [symbol], delta, cash, mode: "put" as const };
      for await (const item of startRun(body, { signal: controller.signal })) {
        latest = applyEvent(latest, item);
        setSteps(latest);
        if (item.type === "run_error") {
          latestError = item.message;
          setError(item.message);
        }
      }
    } catch (err) {
      if (controller.signal.aborted || (err instanceof Error && err.name === "AbortError")) {
        aborted = true;
        return;
      }
      const message = err instanceof Error ? err.message : t("desk.failed");
      latestError = message;
      setError(message);
      latest = applyEvent(latest, { type: "run_error", message, ticker: null, data: {} });
      setSteps(latest);
    } finally {
      if (abortRef.current === controller) abortRef.current = null;
      setRunning(false);
    }
    if (aborted) return;
    const stored = saveCachedRun({
      mode,
      language: lang,
      ticker: symbol,
      delta,
      cash,
      shares,
      costBasis,
      userPrompt: prompt,
      steps: latest,
      error: latestError,
    });
    if (stored) setCachedAt(stored.savedAt);
  }

  return (
    <div className="mx-auto flex min-h-dvh max-w-2xl flex-col px-4 pb-[max(1.5rem,env(safe-area-inset-bottom))] pt-[max(1rem,env(safe-area-inset-top))]">
      <header className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <BrandLockup title={title} onHome={stopRun} />
        <div className="flex shrink-0 items-center gap-2">
          <LangSwitch />
          <Link to="/" onClick={stopRun} className="inline-flex min-h-11 items-center px-2 text-sm text-[var(--mute)]">
            {t("common.back")}
          </Link>
        </div>
      </header>

      <section className="ticket mb-5 px-4 py-3 pl-7">
        <div className="flex min-h-11 items-center gap-2">
          {running ? (
            <p className="min-h-11 min-w-0 flex-1 py-3 font-[family-name:var(--font-mono)] text-sm text-[var(--chalk)]">
              {summary}
            </p>
          ) : (
            <button
              type="button"
              className="min-h-11 min-w-0 flex-1 text-left"
              onClick={() => setConfigOpen((open) => !open)}
            >
              <span className="font-[family-name:var(--font-mono)] text-sm text-[var(--chalk)]">
                {summary}
              </span>
            </button>
          )}
          {!running ? (
            <div className="flex shrink-0 items-center">
              <button
                type="button"
                className="min-h-11 px-2 text-xs text-[var(--mute)]"
                onClick={() => setConfigOpen((open) => !open)}
              >
                {configOpen ? t("desk.collapse") : t("desk.editParams")}
              </button>
              {!configOpen && hasResult ? (
                <button
                  type="button"
                  className="min-h-11 px-2 text-xs text-[var(--brass)]"
                  onClick={() => void runAnalysis(ticker)}
                >
                  {t("desk.rerun")}
                </button>
              ) : null}
            </div>
          ) : null}
        </div>
        {configOpen && !running ? (
          <form onSubmit={onAnalyze} className="mt-3 border-t border-[var(--hairline)] pt-4">
            <label htmlFor="ticker" className="text-xs tracking-wide text-[var(--mute)] uppercase">
              {t("desk.ticker")}
            </label>
            <TickerCombobox id="ticker" value={ticker} onChange={setTicker} />
            <div className="mt-4 grid grid-cols-2 gap-3">
              <label className="block">
                <span className="text-xs tracking-wide text-[var(--mute)] uppercase">{t("desk.delta")}</span>
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
                  <span className="text-xs tracking-wide text-[var(--mute)] uppercase">{t("desk.shares")}</span>
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
                  <span className="text-xs tracking-wide text-[var(--mute)] uppercase">{t("desk.cash")}</span>
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
                <span className="text-xs tracking-wide text-[var(--mute)] uppercase">{t("desk.costBasis")}</span>
                <input
                  type="number"
                  min={0.01}
                  step={0.01}
                  value={costBasis || ""}
                  onChange={(e) => setCostBasis(Number(e.target.value))}
                  placeholder={t("desk.costPlaceholder")}
                  className="mt-2 min-h-11 w-full rounded-sm border border-[var(--hairline)] bg-[var(--night)] px-3 font-[family-name:var(--font-mono)]"
                />
              </label>
            ) : null}
            <button
              type="submit"
              disabled={running || !ticker || (mode === "call" && (shares < 100 || costBasis <= 0))}
              className="mt-4 min-h-11 w-full rounded-sm bg-[var(--brass)] font-semibold text-[var(--night)] disabled:opacity-50"
            >
              {running ? t("desk.running") : t("desk.start")}
            </button>
          </form>
        ) : null}
      </section>

      <div className="flex flex-1 flex-col gap-4">
        {userPrompt ? (
          <div className="ml-8 self-end">
            <div className="rounded-2xl rounded-br-sm bg-[var(--brass)]/15 px-4 py-3 text-sm text-[var(--chalk)]">
              {userPrompt}
            </div>
            {cachedAt && !running ? (
              <p className="mt-1 text-right font-[family-name:var(--font-mono)] text-[11px] text-[var(--mute)]">
                {t("desk.cached", { when: formatCachedAt(cachedAt, dateLocale(lang)) })}
              </p>
            ) : null}
          </div>
        ) : (
          <p className="px-1 text-sm leading-relaxed text-[var(--mute)]">
            {hint}
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
  const { t } = useI18n();
  const live = step.status === "running";
  return (
    <article className={`ticket px-4 py-4 pl-7 ${live ? "ticket-live" : ""}`}>
      <header className="mb-2 flex items-center gap-2">
        <StatusMark status={step.status} />
        <h2 className="font-[family-name:var(--font-display)] text-lg">{stepTitle(step, t)}</h2>
        {live ? (
          <span className="ml-auto font-[family-name:var(--font-mono)] text-[11px] tracking-[0.18em] text-[var(--brass)] uppercase">
            {t("desk.working")}
          </span>
        ) : null}
      </header>
      {live ? <WorkingReel label={step.message} /> : <p className="text-sm text-[var(--mute)]">{step.message}</p>}
      {step.type === "regime" && !live ? <RegimeBlock market={step.market} /> : null}
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

function stepTitle(step: TimelineStep, t: (key: MsgKey, vars?: Record<string, string | number>) => string): string {
  if (step.type === "screen") return t("desk.stepScreen", { ticker: step.ticker ?? "" }).trim();
  if (step.type === "calendar") return t("desk.stepCalendar", { ticker: step.ticker ?? "" }).trim();
  if (step.type === "regime") return t("desk.stepRegime");
  if (step.type === "scout") return t("desk.stepScout");
  if (step.type === "desk") return t("desk.stepDesk");
  if (step.type === "error") return t("desk.stepError");
  return step.type;
}

function Buckets({ snapshot, mode }: { snapshot: TickerSnapshot; mode: "put" | "call" }) {
  const { t } = useI18n();
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
        {t("desk.spotBuckets", { ticker: snapshot.ticker, spot: snapshot.spot.toFixed(2) })}
      </p>
      {lastPrint ? (
        <div className="tape-delay">
          <p className="tape-delay-kicker">{t("desk.lastPrintKicker")}</p>
          <p>{t("desk.lastPrintBody")}</p>
          {ivNote ? <p>{t("desk.ivNote")}</p> : null}
        </div>
      ) : null}
      {otherNotes.length ? (
        <ul className="mt-1 text-[11px] text-[var(--mute)]">
          {otherNotes.map((note) => (
            <li key={note}>{note}</li>
          ))}
        </ul>
      ) : null}
      <QualityPanel snapshot={snapshot} mode={mode} />
      {buckets.length === 0 ? (
        <p className="mt-2 text-sm text-[var(--mute)]">{call ? t("desk.noCalls") : t("desk.noPuts")}</p>
      ) : (
        <table className="bucket-table mt-2 w-full min-w-[26rem] text-left text-xs">
          <thead className="text-[var(--mute)]">
            <tr>
              <th className="py-1 font-medium">{t("desk.colBucket")}</th>
              <th className="py-1 font-medium">{t("desk.colContract")}</th>
              <th className="py-1 font-medium">Δ</th>
              <th className="py-1 font-medium">{t("desk.colPremium")}</th>
              <th className="py-1 font-medium">{t("desk.colScore")}</th>
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
  const { t } = useI18n();
  const spread = bucket.spread
    ? t("desk.spread", { strike: bucket.spread.long.strike, n: bucket.spread.contracts })
    : t("desk.noSpread");
  const last = bucket.csp.quote_source === "last";
  const ivMark =
    bucket.csp.iv_source === "implied"
      ? t("desk.ivImplied")
      : bucket.csp.iv_source === "floored"
        ? t("desk.ivFloored")
        : null;
  return (
    <tr className="border-t border-[var(--hairline)]">
      <td className="py-2">{bucket.bucket}</td>
      <td className="contract-id py-2">{bucket.csp.contract_id}</td>
      <td className="py-2">
        {bucket.csp.delta.toFixed(3)}
        {ivMark ? <span className="quote-mark">{ivMark}</span> : null}
      </td>
      <td className="py-2">
        ${money(bucket.premium_per_contract)}
        {last ? <span className="quote-mark">{t("desk.lastMark")}</span> : null}
      </td>
      <td className="py-2">
        {bucket.score ? t("desk.scoreHint", { total: bucket.score.total }) : "—"}
        {bucket.score?.inside_expected_move ? (
          <div className="text-[10px] text-[var(--skip)]">{t("desk.emInside")}</div>
        ) : null}
      </td>
      <td className="py-2">
        {call ? (
          <>
            {t("desk.contracts", { n: bucket.csp_contracts })}
            <div className="text-[10px] text-[var(--mute)]">
              {t("desk.assignAtStrike", { cash: money(bucket.assignment_cash) })}
            </div>
          </>
        ) : (
          <>
            {t("desk.contracts", { n: bucket.csp_contracts })} · ${money(bucket.assignment_cash)}
            <div className="text-[10px] text-[var(--mute)]">{spread}</div>
          </>
        )}
      </td>
    </tr>
  );
}

function CalendarBlock({ calendar }: { calendar: CalendarGate }) {
  const { t } = useI18n();
  return (
    <div className="mt-3 text-sm">
      <p>
        {t("desk.holding", { start: calendar.holding_start, end: calendar.holding_end })}
      </p>
      {calendar.hard_skip ? (
        <p className="mt-1 text-[var(--skip)]">{calendar.hard_reasons.join("; ") || t("desk.hardSkip")}</p>
      ) : calendar.soft_macros.length ? (
        <p className="mt-1 text-[var(--brass)]">
          {t("desk.softMacro")}{" "}
          {calendar.soft_macros.map((item) => `${item.kind} ${item.event_date}`).join(" · ")}
        </p>
      ) : (
        <p className="mt-1 text-[var(--mute)]">{t("desk.noCalendar")}</p>
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
  const { t } = useI18n();
  if (events.length === 0) {
    return <p className="mt-3 text-sm text-[var(--mute)]">{t("desk.noEvents")}</p>;
  }
  return (
    <ul className="mt-3 space-y-2">
      {events.map((event) => (
        <li key={`${event.title}-${event.expected_time}`} className="text-sm">
          <span className="font-[family-name:var(--font-mono)] text-xs text-[var(--brass)]">
            {event.action} / {event.mechanism}
          </span>
          <p>{event.title}</p>
          <p className="text-xs text-[var(--mute)]">{event.expected_time || t("desk.undated")}</p>
        </li>
      ))}
    </ul>
  );
}

function structureLabel(structure: string | null, t: (key: MsgKey) => string): string {
  if (structure === "BULL_PUT_SPREAD") return t("desk.structSpread");
  if (structure === "COVERED_CALL") return t("desk.structCC");
  if (structure === "CSP") return t("desk.structCSP");
  return structure ?? "";
}

function VerdictCard({ desk, mode }: { desk: DeskOutput; mode: "put" | "call" }) {
  const { t } = useI18n();
  const disclaimer = mode === "call" ? t("desk.callDisclaimer") : t("desk.putDisclaimer");
  return (
    <section className="ticket px-4 py-5 pl-7">
      <p className="font-[family-name:var(--font-mono)] text-[11px] tracking-[0.22em] text-[var(--brass)] uppercase">
        {t("desk.verdict")}
      </p>
      <div className="mt-4 flex flex-col gap-5">
        {desk.decisions.map((decision) => (
          <div key={decision.ticker}>
            <div className="flex items-start justify-between gap-4">
              <div className="min-w-0">
                <p className="font-[family-name:var(--font-mono)] text-sm text-[var(--mute)]">
                  {decision.ticker}
                  {decision.structure ? ` · ${structureLabel(decision.structure, t)}` : ""}
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
      <p className="mt-3 text-xs text-[var(--mute)]">{disclaimer}</p>
    </section>
  );
}
