import { useEffect, useState, type FormEvent, type ReactNode } from "react";
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

function Field({
  label,
  children,
  span = false,
}: {
  label: string;
  children: ReactNode;
  span?: boolean;
}) {
  return (
    <label className={`fill-field${span ? " fill-field-span" : ""}`}>
      <span>{label}</span>
      {children}
    </label>
  );
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

  useEffect(() => {
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") onCancel();
    }
    window.addEventListener("keydown", onKey);
    return () => {
      document.body.style.overflow = previous;
      window.removeEventListener("keydown", onKey);
    };
  }, [onCancel]);

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

  return (
    <div className="fill-overlay">
      <form onSubmit={submit} className="ticket fill-sheet" role="dialog" aria-modal="true" aria-labelledby="fill-sheet-title">
        <header className="fill-sheet-head">
          <p id="fill-sheet-title" className="font-[family-name:var(--font-mono)] text-[11px] tracking-[0.22em] text-[var(--brass)] uppercase">
            {title}
          </p>
          {confirmOpened ? <p className="fill-sheet-hint">{t("positions.draftHint")}</p> : null}
        </header>

        <div className="fill-sheet-body">
          <div className="fill-field fill-field-span">
            <span>{t("positions.strategy")}</span>
            <div className="fill-seg">
              {(["CSP", "COVERED_CALL"] as const).map((value) => (
                <button
                  key={value}
                  type="button"
                  className={strategy === value ? "is-on" : ""}
                  onClick={() => setStrategy(value)}
                >
                  {value === "CSP" ? t("positions.csp") : t("positions.coveredCall")}
                </button>
              ))}
            </div>
          </div>

          <div className="fill-field fill-field-span">
            <span>{t("positions.ticker")}</span>
            <TickerCombobox id="position-ticker" value={ticker} onChange={setTicker} compact />
          </div>

          {strategy === "COVERED_CALL" ? (
            <>
              <Field label={t("positions.shares")}>
                <input type="number" min={100} step={1} value={shares} onChange={(e) => setShares(e.target.value)} />
              </Field>
              <Field label={t("positions.costBasis")}>
                <input type="number" min={0.01} step={0.01} value={costBasis} onChange={(e) => setCostBasis(e.target.value)} />
              </Field>
            </>
          ) : null}

          <Field label={t("positions.expiry")}>
            <input type="date" value={expiry} onChange={(e) => setExpiry(e.target.value)} required />
          </Field>
          <Field label={t("positions.strike")}>
            <input type="number" min={0.01} step={0.01} value={strike} onChange={(e) => setStrike(e.target.value)} />
          </Field>

          <Field label={t("positions.contracts")}>
            <input type="number" min={1} step={1} value={contracts} onChange={(e) => setContracts(e.target.value)} />
          </Field>
          <Field label={confirmOpened ? t("positions.actualEntryPremium") : t("positions.entryPremium")}>
            <input type="number" min={0} step={0.01} value={entryPremium} onChange={(e) => setEntryPremium(e.target.value)} />
          </Field>

          <div className="fill-field fill-field-span">
            <span>{t("positions.assignmentOk")}</span>
            <div className="fill-seg">
              <button type="button" className={assignmentOk ? "is-on" : ""} onClick={() => setAssignmentOk(true)}>
                {t("positions.assignmentYes")}
              </button>
              <button type="button" className={!assignmentOk ? "is-on" : ""} onClick={() => setAssignmentOk(false)}>
                {t("positions.assignmentNo")}
              </button>
            </div>
          </div>

          <Field label={t("positions.openedAt")}>
            <input type="date" value={openedAt} onChange={(e) => setOpenedAt(e.target.value)} />
          </Field>
          <Field label={t("positions.note")}>
            <input value={note} onChange={(e) => setNote(e.target.value)} />
          </Field>

          {error ? <p className="fill-sheet-error">{error}</p> : null}
        </div>

        <div className="fill-sheet-foot">
          {confirmOpened ? (
            <label className="fill-confirm">
              <input type="checkbox" checked={openedConfirm} onChange={(e) => setOpenedConfirm(e.target.checked)} />
              {t("positions.iOpened")}
            </label>
          ) : null}
          <div className="fill-actions">
            <button type="button" className="ghost" onClick={onCancel}>
              {t("positions.cancel")}
            </button>
            <button type="submit" className="stamp-save">
              {t("positions.save")}
            </button>
          </div>
        </div>
      </form>
    </div>
  );
}
