import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { evaluatePositions, fetchRollCandidates } from "./api";
import { BrandLockup } from "./Brand";
import { PositionForm } from "./PositionForm";
import { dateLocale, type MsgKey } from "./i18n";
import { LangSwitch, useI18n } from "./locale";
import {
  addPosition,
  applyImport,
  closePosition,
  deletePosition,
  downloadPositionsJson,
  historyPositions,
  loadPositionSettings,
  loadPositions,
  openPositions,
  parseImportPayload,
  rollPosition,
  savePositionSettings,
  StorageError,
  updatePosition,
  type Position,
  type PositionDraft,
  type PositionEvaluation,
  type PositionSettings,
  type RollCandidate,
} from "./positions";
import { Link } from "./router";

const REFRESH_MS = 120_000;

function money(value: number): string {
  const abs = Math.abs(value).toLocaleString("en-US", { maximumFractionDigits: 0 });
  if (value > 0) return `+$${abs}`;
  if (value < 0) return `-$${abs}`;
  return `$${abs}`;
}

function premium(value: number): string {
  return `$${value.toFixed(2)}`;
}

function pct(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

function formatWhen(iso: string, locale: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleString(locale, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

function formatExpiry(expiry: string, locale: string): string {
  const date = new Date(`${expiry}T00:00:00`);
  if (Number.isNaN(date.getTime())) return expiry;
  return date.toLocaleDateString(locale, { month: "short", day: "numeric" });
}

export function PositionsPage() {
  const { lang, t } = useI18n();
  const locale = dateLocale(lang);
  const [positions, setPositions] = useState<Position[]>([]);
  const [storageError, setStorageError] = useState(false);
  const [settings, setSettings] = useState<PositionSettings>(() => {
    try {
      return loadPositionSettings();
    } catch {
      return { profitTarget: 0.75, nearExpiryDte: 2, nearExpiryProfitTarget: 0.5 };
    }
  });
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [form, setForm] = useState<{ mode: "add" | "edit"; initial?: Position | PositionDraft; confirm?: boolean } | null>(
    null,
  );
  const [evaluations, setEvaluations] = useState<Record<string, PositionEvaluation>>({});
  const [evalError, setEvalError] = useState<string | null>(null);
  const [evalLoading, setEvalLoading] = useState(false);
  const [fetchedAt, setFetchedAt] = useState<string | null>(null);
  const [marketOpen, setMarketOpen] = useState<boolean | null>(null);
  const [closing, setClosing] = useState<Position | null>(null);
  const [rolling, setRolling] = useState<Position | null>(null);
  const [importOpen, setImportOpen] = useState(false);
  const [importMode, setImportMode] = useState<"replace" | "merge">("merge");
  const [importMessage, setImportMessage] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const evalRef = useRef(0);

  const reload = useCallback(() => {
    try {
      setStorageError(false);
      setPositions(loadPositions());
    } catch (err) {
      if (err instanceof StorageError) setStorageError(true);
      else setStorageError(true);
    }
  }, []);

  useEffect(() => {
    reload();
  }, [reload]);

  useEffect(() => {
    const onStorage = (event: StorageEvent) => {
      if (event.key === "option-desk:positions:v1") reload();
    };
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, [reload]);

  const opens = useMemo(() => openPositions(positions), [positions]);
  const sortedOpens = useMemo(() => {
    const rank = { CLOSE: 0, ROLL: 1, HOLD: 2 } as const;
    return opens.slice().sort((a, b) => {
      const left = evaluations[a.id]?.management.action;
      const right = evaluations[b.id]?.management.action;
      const leftRank = left == null ? 3 : rank[left];
      const rightRank = right == null ? 3 : rank[right];
      return leftRank - rightRank;
    });
  }, [opens, evaluations]);
  const history = useMemo(() => historyPositions(positions), [positions]);

  const refreshQuotes = useCallback(
    async (force = false) => {
      if (opens.length === 0) {
        setEvaluations({});
        setFetchedAt(null);
        setEvalError(null);
        return;
      }
      const token = ++evalRef.current;
      setEvalLoading(true);
      if (!force) setEvalError(null);
      try {
        const result = await evaluatePositions(opens, settings);
        if (token !== evalRef.current) return;
        const next: Record<string, PositionEvaluation> = {};
        for (const item of result.evaluations) next[item.positionId] = item;
        setEvaluations(next);
        setFetchedAt(result.fetchedAt);
        setMarketOpen(result.marketOpen);
        setEvalError(null);
      } catch (err) {
        if (token !== evalRef.current) return;
        setEvalError(err instanceof Error ? err.message : t("positions.evaluateFailed"));
      } finally {
        if (token === evalRef.current) setEvalLoading(false);
      }
    },
    [opens, settings, t],
  );

  useEffect(() => {
    void refreshQuotes();
  }, [refreshQuotes]);

  useEffect(() => {
    if (opens.length === 0) return;
    const tick = () => {
      if (document.visibilityState === "visible") void refreshQuotes(true);
    };
    const timer = window.setInterval(tick, REFRESH_MS);
    const onVis = () => {
      if (document.visibilityState === "visible") void refreshQuotes(true);
    };
    document.addEventListener("visibilitychange", onVis);
    return () => {
      window.clearInterval(timer);
      document.removeEventListener("visibilitychange", onVis);
    };
  }, [opens.length, refreshQuotes]);

  const closeCount = opens.filter((item) => evaluations[item.id]?.management.action === "CLOSE").length;
  const rollCount = opens.filter((item) => evaluations[item.id]?.management.action === "ROLL").length;
  const estimatedPnl = opens.reduce((sum, item) => {
    const pnl = evaluations[item.id]?.markPnl;
    return pnl == null ? sum : sum + pnl;
  }, 0);

  function saveDraft(draft: PositionDraft) {
    if (form?.mode === "edit" && form.initial && "id" in form.initial) {
      updatePosition(form.initial.id, {
        ...draft,
        ticker: draft.ticker,
      });
    } else {
      addPosition(draft);
    }
    setForm(null);
    setNotice(t("positions.saved"));
    reload();
  }

  return (
    <div className="mx-auto flex min-h-dvh max-w-2xl flex-col px-4 pb-[max(1.5rem,env(safe-area-inset-bottom))] pt-[max(1rem,env(safe-area-inset-top))]">
      <header className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <BrandLockup title={t("positions.title")} />
        <div className="flex shrink-0 items-center gap-2">
          <LangSwitch />
          <Link to="/" className="inline-flex min-h-11 items-center px-2 text-sm text-[var(--mute)]">
            {t("common.back")}
          </Link>
        </div>
      </header>

      {storageError ? (
        <section className="ticket px-5 py-6 pl-8">
          <h1 className="font-[family-name:var(--font-display)] text-2xl">{t("positions.storageError")}</h1>
          <p className="mt-3 text-sm text-[var(--mute)]">{t("positions.storageErrorHint")}</p>
          <button
            type="button"
            className="mt-5 min-h-11 rounded-sm bg-[var(--brass)] px-4 font-semibold text-[var(--night)]"
            onClick={() => setImportOpen(true)}
          >
            {t("positions.import")}
          </button>
        </section>
      ) : positions.length === 0 ? (
        <section className="ticket px-5 py-6 pl-8">
          <p className="font-[family-name:var(--font-mono)] text-[11px] tracking-[0.22em] text-[var(--brass)] uppercase">
            {t("positions.title")}
          </p>
          <h1 className="mt-3 font-[family-name:var(--font-display)] text-2xl">{t("positions.empty")}</h1>
          <p className="mt-3 text-sm leading-relaxed text-[var(--mute)]">{t("positions.emptyHint")}</p>
          <div className="mt-5 flex flex-col gap-2 sm:flex-row">
            <Link to="/put" className="inline-flex min-h-11 items-center justify-center rounded-sm bg-[var(--brass)] px-4 font-semibold text-[var(--night)]">
              {t("positions.analyzePut")}
            </Link>
            <Link to="/call" className="inline-flex min-h-11 items-center justify-center rounded-sm border border-[var(--hairline)] px-4">
              {t("positions.analyzeCall")}
            </Link>
            <button
              type="button"
              className="min-h-11 rounded-sm border border-[var(--hairline)] px-4"
              onClick={() => setForm({ mode: "add" })}
            >
              + {t("positions.add")}
            </button>
            <button
              type="button"
              className="min-h-11 rounded-sm border border-[var(--hairline)] px-4"
              onClick={() => setImportOpen(true)}
            >
              {t("positions.import")}
            </button>
          </div>
        </section>
      ) : (
        <>
          <section className="ticket mb-4 px-5 py-5 pl-8">
            <p className="font-[family-name:var(--font-mono)] text-[11px] tracking-[0.22em] text-[var(--brass)] uppercase">
              {t("positions.title")}
            </p>
            <p className="mt-3 font-[family-name:var(--font-display)] text-2xl">
              {t("positions.openCount", { n: opens.length })}
            </p>
            <p className="mt-2 text-sm text-[var(--mute)]">
              {t("positions.closeCandidates", { n: closeCount })} · {t("positions.rollCandidateCount", { n: rollCount })}
            </p>
            <p className="mt-3 font-[family-name:var(--font-mono)] text-sm">
              {t("positions.estimatedOptionPnl")}{" "}
              <span className={estimatedPnl >= 0 ? "text-[var(--open)]" : "text-[var(--skip)]"}>{money(estimatedPnl)}</span>
              <span className="ml-2 text-xs text-[var(--mute)]">{t("positions.estimated")}</span>
            </p>
            {marketOpen === false ? <p className="mt-2 text-xs text-[var(--skip)]">{t("positions.marketClosed")}</p> : null}
            {fetchedAt ? (
              <p className="mt-1 font-[family-name:var(--font-mono)] text-[11px] text-[var(--mute)]">
                {t("positions.fetchedAt", { when: formatWhen(fetchedAt, locale) })}
              </p>
            ) : null}
            {evalLoading ? <p className="mt-2 text-xs text-[var(--mute)]">{t("positions.loadingQuotes")}</p> : null}
            {evalError ? <p className="mt-2 text-sm text-[var(--skip)]">{evalError}</p> : null}
            <div className="mt-4 flex flex-wrap gap-2">
              <button type="button" className="min-h-11 rounded-sm bg-[var(--brass)] px-3 text-sm font-semibold text-[var(--night)]" onClick={() => setForm({ mode: "add" })}>
                + {t("positions.add")}
              </button>
              <button type="button" className="min-h-11 rounded-sm border border-[var(--hairline)] px-3 text-sm" onClick={() => setImportOpen(true)}>
                {t("positions.import")}
              </button>
              <button type="button" className="min-h-11 rounded-sm border border-[var(--hairline)] px-3 text-sm" onClick={() => downloadPositionsJson(positions)}>
                {t("positions.export")}
              </button>
              <button type="button" className="min-h-11 rounded-sm border border-[var(--hairline)] px-3 text-sm" onClick={() => void refreshQuotes(true)} disabled={opens.length === 0}>
                {t("positions.refresh")}
              </button>
              <button type="button" className="min-h-11 rounded-sm border border-[var(--hairline)] px-3 text-sm" onClick={() => setSettingsOpen((open) => !open)}>
                {t("positions.settings")}
              </button>
            </div>
            {settingsOpen ? (
              <SettingsPanel
                settings={settings}
                onSave={(next) => {
                  const saved = savePositionSettings(next);
                  setSettings(saved);
                  setNotice(t("positions.settingsSaved"));
                }}
              />
            ) : null}
          </section>

          <div className="flex flex-col gap-4">
            {sortedOpens.map((position) => (
              <PositionCard
                key={position.id}
                position={position}
                evaluation={evaluations[position.id]}
                locale={locale}
                onEdit={() => setForm({ mode: "edit", initial: position })}
                onDelete={() => {
                  if (window.confirm(t("positions.confirmDelete"))) {
                    deletePosition(position.id);
                    reload();
                  }
                }}
                onClose={() => setClosing(position)}
                onRoll={() => setRolling(position)}
              />
            ))}
          </div>

          {history.length > 0 ? (
            <section className="mt-6">
              <p className="mb-3 font-[family-name:var(--font-mono)] text-[11px] tracking-[0.22em] text-[var(--mute)] uppercase">
                {t("positions.history")}
              </p>
              <div className="flex flex-col gap-3">
                {history.map((position) => (
                  <HistoryCard key={position.id} position={position} locale={locale} />
                ))}
              </div>
            </section>
          ) : null}
        </>
      )}

      {notice ? <p className="mt-4 text-sm text-[var(--open)]">{notice}</p> : null}
      {importMessage ? <p className="mt-2 text-sm text-[var(--open)]">{importMessage}</p> : null}

      {form ? (
        <PositionForm
          title={form.mode === "edit" ? t("positions.editTitle") : t("positions.addTitle")}
          initial={form.initial}
          confirmOpened={Boolean(form.confirm)}
          onCancel={() => setForm(null)}
          onSave={saveDraft}
        />
      ) : null}

      {closing ? (
        <CloseDialog
          position={closing}
          evaluation={evaluations[closing.id]}
          onCancel={() => setClosing(null)}
          onConfirm={(closePrice, fees) => {
            closePosition(closing.id, { closePrice, fees });
            setClosing(null);
            reload();
          }}
        />
      ) : null}

      {rolling ? (
        <RollDialog
          position={rolling}
          evaluation={evaluations[rolling.id]}
          onCancel={() => setRolling(null)}
          onConfirm={(payload) => {
            rollPosition(rolling.id, payload);
            setRolling(null);
            reload();
          }}
        />
      ) : null}

      {importOpen ? (
        <ImportDialog
          mode={importMode}
          onMode={setImportMode}
          onCancel={() => setImportOpen(false)}
          onFile={async (file) => {
            try {
              const text = await file.text();
              const incoming = parseImportPayload(JSON.parse(text) as unknown);
              const existing = storageError ? [] : loadPositions();
              applyImport(existing, incoming, importMode);
              setStorageError(false);
              setImportOpen(false);
              setImportMessage(t("positions.importOk", { n: incoming.length }));
              reload();
            } catch {
              setImportMessage(t("positions.importInvalid"));
            }
          }}
        />
      ) : null}
    </div>
  );
}

function translateReason(code: string, translate: (key: MsgKey) => string): string {
  if (code === "PROFIT_TARGET_REACHED") return translate("positions.reasonProfit");
  if (code === "NEAR_EXPIRY_PROFIT") return translate("positions.reasonNearExpiry");
  if (code === "ASSIGNMENT_RISK") return translate("positions.reasonAssignment");
  if (code === "HOLD") return translate("positions.reasonHold");
  return code;
}

function PositionCard({
  position,
  evaluation,
  locale,
  onEdit,
  onDelete,
  onClose,
  onRoll,
}: {
  position: Position;
  evaluation?: PositionEvaluation;
  locale: string;
  onEdit: () => void;
  onDelete: () => void;
  onClose: () => void;
  onRoll: () => void;
}) {
  const { t } = useI18n();
  const right = position.optionType === "CALL" ? "C" : "P";
  const action = evaluation?.management.action ?? null;
  const stamp =
    action === "CLOSE" ? "stamp-open" : action === "ROLL" ? "stamp-roll" : action === "HOLD" ? "stamp-hold" : "stamp-skip";
  const stampText =
    action === "CLOSE"
      ? t("positions.closeCandidate")
      : action === "ROLL"
        ? t("positions.rollCandidate")
        : action === "HOLD"
          ? t("positions.holdCandidate")
          : t("positions.noQuote");
  const reasons = evaluation?.management.reasons ?? [];

  return (
    <article className="ticket px-5 py-5 pl-8">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="font-[family-name:var(--font-mono)] text-sm text-[var(--mute)]">
            {position.ticker} · {position.strategy === "COVERED_CALL" ? t("positions.coveredCall") : t("positions.csp")}
          </p>
          <p className="mt-1 font-[family-name:var(--font-mono)] text-lg">
            {position.strike}
            {right} · {formatExpiry(position.expiry, locale)}
          </p>
          <p className="text-xs text-[var(--mute)]">{t("positions.contractsUnit", { n: position.contracts })}</p>
        </div>
        <span className={`stamp shrink-0 ${stamp}`}>{stampText}</span>
      </div>

      <dl className="position-metrics mt-4 grid grid-cols-2 gap-x-4 gap-y-3 text-sm sm:grid-cols-3">
        <Metric label={t("positions.entryPremium")} value={premium(position.entryPremium)} />
        <Metric label={t("positions.current")} value={evaluation?.contract ? premium(evaluation.contract.mid) : t("positions.none")} />
        <Metric label={t("positions.dte")} value={evaluation?.contract ? String(evaluation.contract.dte) : "—"} />
        <Metric label={t("positions.delta")} value={evaluation?.contract ? evaluation.contract.delta.toFixed(2) : "—"} />
        <Metric
          label={t("positions.profitCapture")}
          value={evaluation?.profitCapture == null ? "—" : pct(evaluation.profitCapture)}
        />
        <Metric
          label={t("positions.estimatedPnl")}
          value={evaluation?.markPnl == null ? "—" : money(evaluation.markPnl)}
          tone={evaluation?.markPnl == null ? undefined : evaluation.markPnl >= 0 ? "up" : "down"}
        />
      </dl>

      {evaluation?.itm != null ? (
        <p className="mt-3 text-xs text-[var(--mute)]">{evaluation.itm ? t("positions.itm") : t("positions.otm")}</p>
      ) : null}
      {evaluation && !evaluation.contract ? (
        <p className="mt-3 text-sm text-[var(--skip)]">{t("positions.managementUnavailable")}</p>
      ) : null}
      {reasons.length > 0 ? (
        <p className="mt-2 text-sm text-[var(--chalk)]">
          {t("positions.reason")}: {reasons.map((code) => translateReason(code, t)).join(" · ")}
        </p>
      ) : null}

      <div className="mt-4 flex flex-wrap gap-2">
        <button type="button" className="min-h-11 rounded-sm bg-[var(--brass)] px-3 text-sm font-semibold text-[var(--night)]" onClick={onClose}>
          {t("positions.closePosition")}
        </button>
        <button type="button" className="min-h-11 rounded-sm border border-[var(--hairline)] px-3 text-sm" onClick={onRoll}>
          {t("positions.roll")}
        </button>
        <button type="button" className="min-h-11 rounded-sm border border-[var(--hairline)] px-3 text-sm" onClick={onEdit}>
          {t("positions.edit")}
        </button>
        <button type="button" className="min-h-11 rounded-sm border border-[var(--hairline)] px-3 text-sm text-[var(--skip)]" onClick={onDelete}>
          {t("positions.delete")}
        </button>
      </div>
    </article>
  );
}

function Metric({ label, value, tone }: { label: string; value: string; tone?: "up" | "down" }) {
  return (
    <div>
      <dt className="font-[family-name:var(--font-mono)] text-[11px] tracking-wide text-[var(--mute)] uppercase">{label}</dt>
      <dd className={`mt-1 font-[family-name:var(--font-mono)] ${tone === "up" ? "text-[var(--open)]" : tone === "down" ? "text-[var(--skip)]" : ""}`}>
        {value}
      </dd>
    </div>
  );
}

function HistoryCard({ position, locale }: { position: Position; locale: string }) {
  const { t } = useI18n();
  const right = position.optionType === "CALL" ? "C" : "P";
  return (
    <article className="ticket px-5 py-4 pl-8 opacity-80">
      <p className="font-[family-name:var(--font-mono)] text-sm">
        {position.ticker} {position.strike}
        {right} · {formatExpiry(position.expiry, locale)} ·{" "}
        {position.status === "ROLLED" ? t("positions.statusRolled") : t("positions.statusClosed")}
      </p>
      {position.realizedPnl != null ? (
        <p className={`mt-1 text-sm ${position.realizedPnl >= 0 ? "text-[var(--open)]" : "text-[var(--skip)]"}`}>
          {t("positions.realizedPnl")} {money(position.realizedPnl)}
        </p>
      ) : null}
    </article>
  );
}

function SettingsPanel({
  settings,
  onSave,
}: {
  settings: PositionSettings;
  onSave: (next: PositionSettings) => void;
}) {
  const { t } = useI18n();
  const [profitTarget, setProfitTarget] = useState(String(Math.round(settings.profitTarget * 100)));
  const [nearExpiryDte, setNearExpiryDte] = useState(String(settings.nearExpiryDte));
  const [nearExpiryProfitTarget, setNearExpiryProfitTarget] = useState(
    String(Math.round(settings.nearExpiryProfitTarget * 100)),
  );
  const field = "mt-2 min-h-11 w-full rounded-sm border border-[var(--hairline)] bg-[var(--night)] px-3 font-[family-name:var(--font-mono)]";
  return (
    <form
      className="mt-4 border-t border-[var(--hairline)] pt-4"
      onSubmit={(event) => {
        event.preventDefault();
        onSave({
          profitTarget: Number(profitTarget) / 100,
          nearExpiryDte: Number(nearExpiryDte),
          nearExpiryProfitTarget: Number(nearExpiryProfitTarget) / 100,
        });
      }}
    >
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <label className="text-xs tracking-wide text-[var(--mute)] uppercase">
          {t("positions.profitTarget")} %
          <input className={field} type="number" min={1} max={99} value={profitTarget} onChange={(e) => setProfitTarget(e.target.value)} />
        </label>
        <label className="text-xs tracking-wide text-[var(--mute)] uppercase">
          {t("positions.nearExpiryDte")}
          <input className={field} type="number" min={0} max={14} value={nearExpiryDte} onChange={(e) => setNearExpiryDte(e.target.value)} />
        </label>
        <label className="text-xs tracking-wide text-[var(--mute)] uppercase">
          {t("positions.nearExpiryProfitTarget")} %
          <input className={field} type="number" min={1} max={99} value={nearExpiryProfitTarget} onChange={(e) => setNearExpiryProfitTarget(e.target.value)} />
        </label>
      </div>
      <button type="submit" className="mt-3 min-h-11 rounded-sm bg-[var(--brass)] px-4 text-sm font-semibold text-[var(--night)]">
        {t("common.save")}
      </button>
    </form>
  );
}

function CloseDialog({
  position,
  evaluation,
  onCancel,
  onConfirm,
}: {
  position: Position;
  evaluation?: PositionEvaluation;
  onCancel: () => void;
  onConfirm: (closePrice: number, fees: number) => void;
}) {
  const { t } = useI18n();
  const estimate = evaluation?.estimatedClosePrice ?? evaluation?.contract?.ask ?? evaluation?.contract?.mid ?? "";
  const [closePrice, setClosePrice] = useState(estimate === "" ? "" : String(estimate));
  const [fees, setFees] = useState("0");
  const field = "mt-2 min-h-11 w-full rounded-sm border border-[var(--hairline)] bg-[var(--night)] px-3 font-[family-name:var(--font-mono)]";
  return (
    <div className="fixed inset-0 z-40 flex items-end justify-center bg-black/55 p-3 sm:items-center">
      <form
        className="ticket w-full max-w-md px-5 py-5 pl-8"
        onSubmit={(event) => {
          event.preventDefault();
          const price = Number(closePrice);
          if (!(price >= 0)) return;
          onConfirm(price, Number(fees) || 0);
        }}
      >
        <p className="font-[family-name:var(--font-mono)] text-[11px] tracking-[0.22em] text-[var(--brass)] uppercase">
          {t("positions.confirmClose")}
        </p>
        <p className="mt-3 font-[family-name:var(--font-mono)]">
          {position.ticker} {position.strike}
          {position.optionType === "CALL" ? "C" : "P"}
        </p>
        <p className="mt-2 text-sm text-[var(--mute)]">
          {t("positions.currentMark")} {evaluation?.contract ? premium(evaluation.contract.mid) : "—"}
        </p>
        <p className="text-sm text-[var(--mute)]">
          {t("positions.estimatedClose")} {evaluation?.estimatedClosePrice != null ? premium(evaluation.estimatedClosePrice) : "—"}
        </p>
        <p className="text-sm text-[var(--mute)]">
          {t("positions.currentEstimatedPnl")} {evaluation?.estimatedClosePnl != null ? money(evaluation.estimatedClosePnl) : "—"}
          <span className="ml-1 text-xs">{t("positions.estimated")}</span>
        </p>
        <label className="mt-4 block text-xs tracking-wide text-[var(--mute)] uppercase">
          {t("positions.actualClosePrice")}
          <input className={field} type="number" min={0} step={0.01} value={closePrice} onChange={(e) => setClosePrice(e.target.value)} />
        </label>
        <label className="mt-3 block text-xs tracking-wide text-[var(--mute)] uppercase">
          {t("positions.fees")}
          <input className={field} type="number" min={0} step={0.01} value={fees} onChange={(e) => setFees(e.target.value)} />
        </label>
        <div className="mt-5 flex gap-3">
          <button type="button" className="min-h-11 flex-1 rounded-sm border border-[var(--hairline)]" onClick={onCancel}>
            {t("common.cancel")}
          </button>
          <button type="submit" className="min-h-11 flex-1 rounded-sm bg-[var(--brass)] font-semibold text-[var(--night)]">
            {t("positions.confirmClose")}
          </button>
        </div>
      </form>
    </div>
  );
}

function RollDialog({
  position,
  evaluation,
  onCancel,
  onConfirm,
}: {
  position: Position;
  evaluation?: PositionEvaluation;
  onCancel: () => void;
  onConfirm: (payload: { closePrice: number; newPremium: number; newExpiry: string; newStrike: number; fees?: number }) => void;
}) {
  const { t, lang } = useI18n();
  const locale = dateLocale(lang);
  const [candidates, setCandidates] = useState<RollCandidate[]>([]);
  const [current, setCurrent] = useState(evaluation?.contract ?? null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [picked, setPicked] = useState<RollCandidate | null>(null);
  const [closePrice, setClosePrice] = useState(
    evaluation?.estimatedClosePrice != null ? String(evaluation.estimatedClosePrice) : "",
  );
  const [newPremium, setNewPremium] = useState("");
  const [fees, setFees] = useState("0");
  const field = "mt-2 min-h-11 w-full rounded-sm border border-[var(--hairline)] bg-[var(--night)] px-3 font-[family-name:var(--font-mono)]";

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const result = await fetchRollCandidates(position, evaluation?.estimatedClosePrice ?? null);
        if (cancelled) return;
        setCandidates(result.candidates);
        setCurrent(result.current);
        const rec = result.candidates.find((item) => item.recommended) ?? result.candidates[0] ?? null;
        setPicked(rec);
        if (rec) setNewPremium(String(rec.contract.mid));
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : t("positions.rollFailed"));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [position, evaluation?.estimatedClosePrice, t]);

  return (
    <div className="fixed inset-0 z-40 flex items-end justify-center bg-black/55 p-3 sm:items-center">
      <form
        className="ticket max-h-[min(92dvh,44rem)] w-full max-w-lg overflow-y-auto px-5 py-5 pl-8"
        onSubmit={(event) => {
          event.preventDefault();
          if (!picked) return;
          const close = Number(closePrice);
          const premiumIn = Number(newPremium);
          if (!(close >= 0) || !(premiumIn >= 0)) return;
          onConfirm({
            closePrice: close,
            newPremium: premiumIn,
            newExpiry: picked.contract.expiry,
            newStrike: picked.contract.strike,
            fees: Number(fees) || 0,
          });
        }}
      >
        <p className="font-[family-name:var(--font-mono)] text-[11px] tracking-[0.22em] text-[var(--brass)] uppercase">
          {t("positions.rollCandidates")}
        </p>
        <p className="mt-3 text-sm text-[var(--mute)]">{t("positions.currentContract")}</p>
        <p className="font-[family-name:var(--font-mono)]">
          {position.ticker} {position.strike}
          {position.optionType === "CALL" ? "C" : "P"} {formatExpiry(position.expiry, locale)}
          {current ? ` · DTE ${current.dte} · Δ ${current.delta.toFixed(2)} · ${premium(current.mid)}` : ""}
        </p>
        {loading ? <p className="mt-3 text-sm text-[var(--mute)]">{t("positions.loadingQuotes")}</p> : null}
        {error ? <p className="mt-3 text-sm text-[var(--skip)]">{error}</p> : null}
        {!loading && candidates.length === 0 ? <p className="mt-3 text-sm text-[var(--mute)]">{t("positions.noCandidates")}</p> : null}
        <ul className="mt-3 space-y-2">
          {candidates.map((item) => {
            const selected = picked?.contract.contract_id === item.contract.contract_id;
            const net = item.estimatedNet;
            return (
              <li key={item.contract.contract_id}>
                <button
                  type="button"
                  className={`w-full rounded-sm border px-3 py-3 text-left ${selected ? "border-[var(--brass)]" : "border-[var(--hairline)]"}`}
                  onClick={() => {
                    setPicked(item);
                    setNewPremium(String(item.contract.mid));
                  }}
                >
                  <p className="font-[family-name:var(--font-mono)] text-sm">
                    {formatExpiry(item.contract.expiry, locale)} {item.contract.strike}
                    {position.optionType === "CALL" ? "C" : "P"} · Δ {item.contract.delta.toFixed(2)} · {premium(item.contract.mid)}
                  </p>
                  {net != null ? (
                    <p className={`mt-1 text-xs ${net >= 0 ? "text-[var(--open)]" : "text-[var(--skip)]"}`}>
                      {net >= 0 ? t("positions.netCredit") : t("positions.netDebit")} {money(net)}
                    </p>
                  ) : null}
                  {item.recommended ? <p className="mt-1 text-[11px] text-[var(--brass)]">{t("positions.recommended")}</p> : null}
                </button>
              </li>
            );
          })}
        </ul>
        <label className="mt-4 block text-xs tracking-wide text-[var(--mute)] uppercase">
          {t("positions.actualClosePrice")}
          <input className={field} type="number" min={0} step={0.01} value={closePrice} onChange={(e) => setClosePrice(e.target.value)} />
        </label>
        <label className="mt-3 block text-xs tracking-wide text-[var(--mute)] uppercase">
          {t("positions.actualNewPremium")}
          <input className={field} type="number" min={0} step={0.01} value={newPremium} onChange={(e) => setNewPremium(e.target.value)} />
        </label>
        <label className="mt-3 block text-xs tracking-wide text-[var(--mute)] uppercase">
          {t("positions.fees")}
          <input className={field} type="number" min={0} step={0.01} value={fees} onChange={(e) => setFees(e.target.value)} />
        </label>
        <div className="mt-5 flex gap-3">
          <button type="button" className="min-h-11 flex-1 rounded-sm border border-[var(--hairline)]" onClick={onCancel}>
            {t("common.cancel")}
          </button>
          <button type="submit" disabled={!picked} className="min-h-11 flex-1 rounded-sm bg-[var(--brass)] font-semibold text-[var(--night)] disabled:opacity-50">
            {t("positions.confirmRoll")}
          </button>
        </div>
      </form>
    </div>
  );
}

function ImportDialog({
  mode,
  onMode,
  onCancel,
  onFile,
}: {
  mode: "replace" | "merge";
  onMode: (mode: "replace" | "merge") => void;
  onCancel: () => void;
  onFile: (file: File) => void;
}) {
  const { t } = useI18n();
  return (
    <div className="fixed inset-0 z-40 flex items-end justify-center bg-black/55 p-3 sm:items-center">
      <div className="ticket w-full max-w-md px-5 py-5 pl-8">
        <p className="font-[family-name:var(--font-mono)] text-[11px] tracking-[0.22em] text-[var(--brass)] uppercase">
          {t("positions.import")}
        </p>
        <p className="mt-3 text-xs tracking-wide text-[var(--mute)] uppercase">{t("positions.importMode")}</p>
        <div className="mt-2 grid grid-cols-2 gap-2">
          <button
            type="button"
            className={`min-h-11 rounded-sm border px-3 text-sm ${mode === "merge" ? "border-[var(--brass)] bg-[var(--brass)] text-[var(--night)]" : "border-[var(--hairline)]"}`}
            onClick={() => onMode("merge")}
          >
            {t("positions.importMerge")}
          </button>
          <button
            type="button"
            className={`min-h-11 rounded-sm border px-3 text-sm ${mode === "replace" ? "border-[var(--brass)] bg-[var(--brass)] text-[var(--night)]" : "border-[var(--hairline)]"}`}
            onClick={() => onMode("replace")}
          >
            {t("positions.importReplace")}
          </button>
        </div>
        <label className="mt-4 inline-flex min-h-11 w-full cursor-pointer items-center justify-center rounded-sm bg-[var(--brass)] font-semibold text-[var(--night)]">
          {t("positions.chooseFile")}
          <input
            type="file"
            accept="application/json,.json"
            className="hidden"
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (file) onFile(file);
            }}
          />
        </label>
        <button type="button" className="mt-3 min-h-11 w-full rounded-sm border border-[var(--hairline)]" onClick={onCancel}>
          {t("common.cancel")}
        </button>
      </div>
    </div>
  );
}
