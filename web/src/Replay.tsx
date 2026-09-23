import { useEffect, useState } from "react";
import { fetchDemos, startReplay, type DemoSummary } from "./api";
import { BrandLockup } from "./Brand";
import { applyEvent, StepCard } from "./Desk";
import { PayoffChart } from "./PayoffChart";
import type { MsgKey } from "./i18n";
import { LangSwitch, useI18n } from "./locale";
import { Link } from "./router";
import type { DeskOutput, StreamEvent, TickerDecision, TimelineStep } from "./types";

type RewriteChange = {
  field: "action" | "structure" | "delta_bucket" | "contract_id";
  before: string;
  after: string;
  changed: boolean;
};

type Rewrite = {
  scenario: string;
  rule: string;
  changes: RewriteChange[];
};

const FIELD_KEY: Record<RewriteChange["field"], MsgKey> = {
  action: "replay.fieldAction",
  structure: "replay.fieldStructure",
  delta_bucket: "replay.fieldBucket",
  contract_id: "replay.fieldContract",
};

function prefersReducedMotion(): boolean {
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

function wait(ms: number, signal: AbortSignal): Promise<void> {
  if (ms <= 0) return Promise.resolve();
  return new Promise((resolve, reject) => {
    const timer = window.setTimeout(resolve, ms);
    const onAbort = () => {
      window.clearTimeout(timer);
      reject(new DOMException("Aborted", "AbortError"));
    };
    if (signal.aborted) {
      onAbort();
      return;
    }
    signal.addEventListener("abort", onAbort, { once: true });
  });
}

export function ReplayIndex() {
  const { t } = useI18n();
  const [scenarios, setScenarios] = useState<DemoSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchDemos()
      .then((items) => {
        if (!cancelled) setScenarios(items);
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(err instanceof Error ? err.message : t("replay.loadFailed"));
      });
    return () => {
      cancelled = true;
    };
  }, [t]);

  return (
    <div className="mx-auto flex min-h-dvh max-w-2xl flex-col px-4 pb-[max(1.5rem,env(safe-area-inset-bottom))] pt-[max(1rem,env(safe-area-inset-top))]">
      <header className="mb-8 flex flex-wrap items-center justify-between gap-3">
        <BrandLockup title={t("replay.title")} />
        <div className="flex shrink-0 items-center gap-2">
          <LangSwitch />
          <Link to="/" className="inline-flex min-h-11 items-center px-2 text-sm text-[var(--mute)]">
            {t("common.back")}
          </Link>
        </div>
      </header>
      <p className="mb-6 max-w-md text-sm leading-relaxed text-[var(--mute)]">{t("replay.lead")}</p>
      {error ? <p className="text-sm text-[var(--skip)]">{error}</p> : null}
      {scenarios == null && !error ? (
        <p className="font-[family-name:var(--font-mono)] text-sm text-[var(--mute)]">{t("replay.loading")}</p>
      ) : null}
      <div className="flex flex-col gap-4">
        {(scenarios ?? []).map((item, index) => (
          <Link key={item.id} to={`/replay/${item.id}`} className="ticket home-gate px-5 py-6 pl-8 text-left">
            <p className="font-[family-name:var(--font-mono)] text-[11px] tracking-[0.26em] text-[var(--brass)] uppercase">
              {String(index + 1).padStart(2, "0")} · {item.kicker}
            </p>
            <h2 className="mt-3 font-[family-name:var(--font-display)] text-[1.7rem] leading-none text-[var(--chalk)]">
              {item.title}
            </h2>
            <p className="mt-3 max-w-sm text-sm leading-relaxed text-[var(--mute)]">{item.summary}</p>
            <span className="mt-5 inline-flex min-h-11 items-center font-[family-name:var(--font-mono)] text-sm text-[var(--brass)]">
              {t("replay.play")} →
            </span>
          </Link>
        ))}
      </div>
    </div>
  );
}

export function ReplayPlayer({ scenario }: { scenario: string }) {
  const { t } = useI18n();
  const [catalog, setCatalog] = useState<DemoSummary[]>([]);
  const [steps, setSteps] = useState<TimelineStep[]>([]);
  const [proposal, setProposal] = useState<DeskOutput | null>(null);
  const [stamped, setStamped] = useState<DeskOutput | null>(null);
  const [rewrite, setRewrite] = useState<Rewrite | null>(null);
  const [heading, setHeading] = useState<string>("");
  const [summary, setSummary] = useState<string>("");
  const [running, setRunning] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [runId, setRunId] = useState(0);

  useEffect(() => {
    let cancelled = false;
    fetchDemos()
      .then((items) => {
        if (cancelled) return;
        setCatalog(items);
        const match = items.find((item) => item.id === scenario);
        if (match) {
          setHeading(match.title);
          setSummary(match.summary);
        }
      })
      .catch(() => {
        /* the stream reports a missing scenario */
      });
    return () => {
      cancelled = true;
    };
  }, [scenario]);

  useEffect(() => {
    const controller = new AbortController();
    const gap = prefersReducedMotion() ? 0 : 320;

    async function play() {
      setRunning(true);
      setError(null);
      setSteps([]);
      setProposal(null);
      setStamped(null);
      setRewrite(null);
      let latest: TimelineStep[] = [];
      try {
        for await (const item of startReplay(scenario, { signal: controller.signal })) {
          if (item.type === "run_started") {
            const title = item.data.title;
            const blurb = item.data.summary;
            if (typeof title === "string") setHeading(title);
            if (typeof blurb === "string") setSummary(blurb);
          }
          if (item.type === "desk_done") {
            setProposal(item.data.proposal as DeskOutput);
            setStamped(item.data.desk as DeskOutput);
            setRewrite(item.data.rewrite as Rewrite);
          }
          latest = applyEvent(latest, item as StreamEvent);
          setSteps(latest);
          if (item.type === "run_error") setError(item.message);
          if (item.type !== "run_started" && item.type !== "run_finished" && item.type !== "run_error") {
            await wait(gap, controller.signal);
          }
        }
      } catch (err) {
        if (controller.signal.aborted || (err instanceof Error && err.name === "AbortError")) return;
        setError(err instanceof Error ? err.message : t("replay.loadFailed"));
      } finally {
        if (!controller.signal.aborted) setRunning(false);
      }
    }

    void play();
    return () => controller.abort();
  }, [scenario, runId, t]);

  const current = catalog.find((item) => item.id === scenario);
  const title = heading || current?.title || scenario;

  return (
    <div className="mx-auto flex min-h-dvh max-w-2xl flex-col px-4 pb-[max(1.5rem,env(safe-area-inset-bottom))] pt-[max(1rem,env(safe-area-inset-top))]">
      <header className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <BrandLockup title={title} />
        <div className="flex shrink-0 items-center gap-2">
          <LangSwitch />
          <Link to="/replay" className="inline-flex min-h-11 items-center px-2 text-sm text-[var(--mute)]">
            {t("common.back")}
          </Link>
        </div>
      </header>

      <section className="ticket mb-5 px-4 py-4 pl-7">
        <p className="font-[family-name:var(--font-mono)] text-[11px] tracking-[0.22em] text-[var(--brass)] uppercase">
          {current?.kicker ?? t("replay.recorded")}
          {running ? ` · ${t("replay.working")}` : ""}
        </p>
        <p className="mt-3 text-sm leading-relaxed text-[var(--mute)]">{summary || t("replay.lead")}</p>
        {!running ? (
          <button
            type="button"
            className="mt-3 min-h-11 px-1 text-sm text-[var(--brass)]"
            onClick={() => setRunId((value) => value + 1)}
          >
            {t("replay.again")}
          </button>
        ) : null}
      </section>

      <div className="flex flex-1 flex-col gap-4">
        {steps.map((step) => (
          <StepCard key={step.id} step={step} mode="put" />
        ))}
        {error ? <p className="text-sm text-[var(--skip)]">{error}</p> : null}
        {proposal && stamped && rewrite ? (
          <RewriteCard proposal={proposal} stamped={stamped} rewrite={rewrite} />
        ) : null}
      </div>

      {catalog.length > 1 ? (
        <nav className="mt-6 flex flex-col gap-2 border-t border-[var(--hairline)] pt-4">
          {catalog
            .filter((item) => item.id !== scenario)
            .map((item) => (
              <Link
                key={item.id}
                to={`/replay/${item.id}`}
                className="inline-flex min-h-11 items-center text-sm text-[var(--brass)]"
              >
                {item.title} →
              </Link>
            ))}
        </nav>
      ) : null}
    </div>
  );
}

function RewriteCard({
  proposal,
  stamped,
  rewrite,
}: {
  proposal: DeskOutput;
  stamped: DeskOutput;
  rewrite: Rewrite;
}) {
  const { t } = useI18n();
  const before = proposal.decisions[0];
  const after = stamped.decisions[0];
  const changed = rewrite.changes.filter((row) => row.changed);
  if (!before || !after) return null;

  return (
    <section className="ticket px-4 py-5 pl-7">
      <p className="font-[family-name:var(--font-mono)] text-[11px] tracking-[0.22em] text-[var(--brass)] uppercase">
        {t("replay.rewrite")}
      </p>
      <p className="mt-3 text-sm leading-relaxed text-[var(--chalk)]">{rewrite.rule}</p>
      <div className="replay-split mt-4">
        <Slip
          label={t("replay.model")}
          decision={before}
          struck={!after.contract_id && Boolean(before.contract_id)}
        />
        <p className="replay-arrow">{t("replay.arrow")}</p>
        <Slip label={t("replay.ruled")} decision={after} ruled struck={false} />
      </div>
      {changed.length ? (
        <dl className="mt-4 border-t border-[var(--hairline)] pt-3">
          <dt className="font-[family-name:var(--font-mono)] text-[11px] tracking-[0.16em] text-[var(--mute)] uppercase">
            {t("replay.changed")}
          </dt>
          {changed.map((row) => (
            <div key={row.field} className="mt-2 grid grid-cols-[5.5rem_1fr] gap-2 text-sm">
              <dt className="text-[var(--mute)]">{t(FIELD_KEY[row.field])}</dt>
              <dd className="min-w-0 font-[family-name:var(--font-mono)]">
                <span className="text-[var(--skip)] line-through">{row.before || t("replay.empty")}</span>
                <span className="mx-2 text-[var(--mute)]">→</span>
                <span className="text-[var(--brass)] break-all">{row.after || t("replay.empty")}</span>
              </dd>
            </div>
          ))}
        </dl>
      ) : null}
      {stamped.portfolio_note ? (
        <p className="mt-4 text-xs leading-relaxed text-[var(--mute)]">{stamped.portfolio_note}</p>
      ) : null}
      {after.action === "OPEN" && after.payoff ? (
        <div className="mt-4">
          <p className="mb-2 font-[family-name:var(--font-mono)] text-[11px] tracking-[0.16em] text-[var(--mute)] uppercase">
            {t("replay.payoff")}
          </p>
          <PayoffChart ticker={after.ticker} payoff={after.payoff} />
        </div>
      ) : null}
    </section>
  );
}

function Slip({
  label,
  decision,
  struck,
  ruled = false,
}: {
  label: string;
  decision: TickerDecision;
  struck: boolean;
  ruled?: boolean;
}) {
  const { t } = useI18n();
  const open = decision.action === "OPEN";
  return (
    <article className={`replay-slip ${ruled ? "is-ruled" : ""} ${open ? "" : "is-skip"}`}>
      <p className="font-[family-name:var(--font-mono)] text-[11px] tracking-[0.16em] text-[var(--mute)] uppercase">
        {label}
      </p>
      <div className="mt-3 flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="font-[family-name:var(--font-mono)] text-xs text-[var(--mute)]">
            {decision.ticker}
            {decision.structure ? ` · ${decision.structure}` : ""}
            {decision.delta_bucket ? ` · ${decision.delta_bucket}` : ""}
          </p>
          <p
            className={`mt-1 break-all font-[family-name:var(--font-mono)] text-sm ${
              struck ? "text-[var(--skip)] line-through" : "text-[var(--chalk)]"
            }`}
          >
            {decision.contract_id || t("replay.empty")}
          </p>
        </div>
        <span className={`stamp shrink-0 ${open ? "stamp-open" : "stamp-skip"}`}>{decision.action}</span>
      </div>
      <p className="mt-3 text-sm leading-relaxed text-[var(--chalk)]">{decision.why}</p>
    </article>
  );
}
