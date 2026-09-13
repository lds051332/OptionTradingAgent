import { useEffect, useState, type FormEvent } from "react";
import { TickerCombobox, normalizeSymbol } from "./TickerCombobox";
import { useI18n } from "./locale";
import type { Position, PositionDraft, PositionStrategy } from "./positions";

type Props = {
  title: string;
  initial?: Partial<PositionDraft> | Position;
  confirmOpened?: boolean;
  onCancel: () => void;
  onSave: (draft: PositionDraft) => void;
};

function toDateInput(iso?: string): string {
  if (!iso) return new Date().toISOString().slice(0, 10);
  return iso.slice(0, 10);
}

export function PositionForm({ title, initial, confirmOpened = false, onCancel, onSave }: Props) {
  const { t } = useI18n();
  const [strategy, setStrategy] = useState<PositionStrategy>(initial?.strategy ?? "CSP");
  const [ticker, setTicker] = useState(initial?.ticker ?? "");
  const [expiry, setExpiry] = useState(initial?.expiry ?? "");
  const [strike, setStrike] = useState(initial?.strike ? String(initial.strike) : "");
  const [contracts, setContracts] = useState(initial?.contracts ? String(initial.contracts) : "1");
  const [entryPremium, setEntryPremium] = useState(
    initial?.entryPremium != null ? String(initial.entryPremium) : "",
  );
  const [assignmentOk, setAssignmentOk] = useState(initial?.assignmentOk ?? true);
  const [openedAt, setOpenedAt] = useState(toDateInput(initial?.openedAt));
  const [note, setNote] = useState(initial?.note ?? "");
  const [shares, setShares] = useState(initial?.shares ? String(initial.shares) : "");
  const [costBasis, setCostBasis] = useState(initial?.costBasis ? String(initial.costBasis) : "");
  const [openedConfirm, setOpenedConfirm] = useState(!confirmOpened);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (strategy === "CSP") {
      setShares("");
      setCostBasis("");
    }
  }, [strategy]);

  function submit(event: FormEvent) {
    event.preventDefault();
    const symbol = normalizeSymbol(ticker);
    const strikeNum = Number(strike);
    const contractsNum = Number(contracts);
    const premiumNum = Number(entryPremium);
    const sharesNum = Number(shares);
    const basisNum = Number(costBasis);
    if (!symbol || !expiry || strikeNum <= 0 || contractsNum < 1 || premiumNum < 0) {
      setError(t("positions.required"));
      return;
    }
    if (strategy === "COVERED_CALL" && (sharesNum < 100 || basisNum <= 0)) {
      setError(t("positions.required"));
      return;
    }
    if (confirmOpened && !openedConfirm) {
      setError(t("positions.iOpened"));
      return;
    }
    onSave({
      ticker: symbol,
      strategy,
      optionType: strategy === "COVERED_CALL" ? "CALL" : "PUT",
      expiry,
      strike: strikeNum,
      contracts: Math.round(contractsNum),
      entryPremium: premiumNum,
      assignmentOk,
      openedAt: new Date(`${openedAt}T12:00:00`).toISOString(),
      shares: strategy === "COVERED_CALL" ? sharesNum : undefined,
      costBasis: strategy === "COVERED_CALL" ? basisNum : undefined,
      note: note.trim() || undefined,
    });
  }

  const field = "mt-2 min-h-11 w-full rounded-sm border border-[var(--hairline)] bg-[var(--night)] px-3 font-[family-name:var(--font-mono)]";
  const label = "text-xs tracking-wide text-[var(--mute)] uppercase";

  return (
    <div className="fixed inset-0 z-40 flex items-end justify-center bg-black/55 p-3 sm:items-center">
      <form
        onSubmit={submit}
        className="ticket max-h-[min(92dvh,44rem)] w-full max-w-lg overflow-y-auto px-5 py-5 pl-8"
      >
        <p className="font-[family-name:var(--font-mono)] text-[11px] tracking-[0.22em] text-[var(--brass)] uppercase">
          {title}
        </p>
        {confirmOpened ? <p className="mt-2 text-sm text-[var(--mute)]">{t("positions.draftHint")}</p> : null}

        <label className={`mt-4 block ${label}`}>{t("positions.strategy")}</label>
        <div className="mt-2 grid grid-cols-2 gap-2">
          {(["CSP", "COVERED_CALL"] as const).map((value) => (
            <button
              key={value}
              type="button"
              className={`min-h-11 rounded-sm border px-3 text-sm ${
                strategy === value
                  ? "border-[var(--brass)] bg-[var(--brass)] text-[var(--night)]"
                  : "border-[var(--hairline)] text-[var(--chalk)]"
              }`}
              onClick={() => setStrategy(value)}
            >
              {value === "CSP" ? t("positions.csp") : t("positions.coveredCall")}
            </button>
          ))}
        </div>

        <label className={`mt-4 block ${label}`} htmlFor="position-ticker">
          {t("positions.ticker")}
        </label>
        <TickerCombobox id="position-ticker" value={ticker} onChange={setTicker} />

        {strategy === "COVERED_CALL" ? (
          <div className="mt-4 grid grid-cols-2 gap-3">
            <label className="block">
              <span className={label}>{t("positions.shares")}</span>
              <input className={field} type="number" min={100} step={1} value={shares} onChange={(e) => setShares(e.target.value)} />
            </label>
            <label className="block">
              <span className={label}>{t("positions.costBasis")}</span>
              <input className={field} type="number" min={0.01} step={0.01} value={costBasis} onChange={(e) => setCostBasis(e.target.value)} />
            </label>
          </div>
        ) : null}

        <div className="mt-4 grid grid-cols-2 gap-3">
          <label className="block">
            <span className={label}>{t("positions.expiry")}</span>
            <input className={field} type="date" value={expiry} onChange={(e) => setExpiry(e.target.value)} required />
          </label>
          <label className="block">
            <span className={label}>{t("positions.strike")}</span>
            <input className={field} type="number" min={0.01} step={0.01} value={strike} onChange={(e) => setStrike(e.target.value)} />
          </label>
        </div>

        <div className="mt-4 grid grid-cols-2 gap-3">
          <label className="block">
            <span className={label}>{t("positions.contracts")}</span>
            <input className={field} type="number" min={1} step={1} value={contracts} onChange={(e) => setContracts(e.target.value)} />
          </label>
          <label className="block">
            <span className={label}>
              {confirmOpened ? t("positions.actualEntryPremium") : t("positions.entryPremium")}
            </span>
            <input className={field} type="number" min={0} step={0.01} value={entryPremium} onChange={(e) => setEntryPremium(e.target.value)} />
          </label>
        </div>

        <label className={`mt-4 block ${label}`}>{t("positions.assignmentOk")}</label>
        <div className="mt-2 grid grid-cols-2 gap-2">
          <button
            type="button"
            className={`min-h-11 rounded-sm border px-3 text-sm ${assignmentOk ? "border-[var(--brass)] bg-[var(--brass)] text-[var(--night)]" : "border-[var(--hairline)]"}`}
            onClick={() => setAssignmentOk(true)}
          >
            {t("positions.assignmentYes")}
          </button>
          <button
            type="button"
            className={`min-h-11 rounded-sm border px-3 text-sm ${!assignmentOk ? "border-[var(--brass)] bg-[var(--brass)] text-[var(--night)]" : "border-[var(--hairline)]"}`}
            onClick={() => setAssignmentOk(false)}
          >
            {t("positions.assignmentNo")}
          </button>
        </div>

        <label className={`mt-4 block ${label}`}>
          {t("positions.openedAt")}
          <input className={field} type="date" value={openedAt} onChange={(e) => setOpenedAt(e.target.value)} />
        </label>
        <label className={`mt-4 block ${label}`}>
          {t("positions.note")}
          <input className={field} value={note} onChange={(e) => setNote(e.target.value)} />
        </label>

        {confirmOpened ? (
          <label className="mt-4 flex min-h-11 items-center gap-3 text-sm">
            <input type="checkbox" checked={openedConfirm} onChange={(e) => setOpenedConfirm(e.target.checked)} />
            {t("positions.iOpened")}
          </label>
        ) : null}

        {error ? <p className="mt-3 text-sm text-[var(--skip)]">{error}</p> : null}

        <div className="mt-5 flex gap-3">
          <button type="button" className="min-h-11 flex-1 rounded-sm border border-[var(--hairline)] text-sm" onClick={onCancel}>
            {t("positions.cancel")}
          </button>
          <button type="submit" className="min-h-11 flex-1 rounded-sm bg-[var(--brass)] font-semibold text-[var(--night)]">
            {t("positions.save")}
          </button>
        </div>
      </form>
    </div>
  );
}
