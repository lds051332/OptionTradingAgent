import type { BucketCandidate, IvContext, MarketRegime, TickerSnapshot } from "./types";
import type { MsgKey } from "./i18n";
import { useI18n } from "./locale";

function pct(value: number | null | undefined): string {
  if (value == null) return "—";
  return `${Math.round(value * 100)}%`;
}

function ivRegimeKey(regime: IvContext["regime"]): MsgKey {
  if (regime === "low") return "desk.ivLow";
  if (regime === "high") return "desk.ivHigh";
  if (regime === "rich") return "desk.ivRich";
  if (regime === "normal") return "desk.ivNormal";
  return "desk.ivUnknown";
}

export function marketLabelKey(label: MarketRegime["label"]): MsgKey {
  if (label === "risk_on") return "desk.marketRiskOn";
  if (label === "caution") return "desk.marketCaution";
  if (label === "risk_off") return "desk.marketRiskOff";
  return "desk.marketNeutral";
}

export function RegimeBlock({ market }: { market?: MarketRegime }) {
  const { t } = useI18n();
  if (!market) {
    return <p className="mt-3 text-sm text-[var(--mute)]">{t("desk.regimeUnavailable")}</p>;
  }
  const tone =
    market.label === "risk_off" || market.label === "caution"
      ? "is-caution"
      : market.label === "risk_on"
        ? "is-open"
        : "";
  return (
    <div className={`regime-strip mt-3 ${tone}`}>
      <p className="regime-label">{t(marketLabelKey(market.label))}</p>
      <p className="regime-why">{market.why || (market.vix != null ? `VIX ${market.vix.toFixed(1)}` : "")}</p>
    </div>
  );
}

export function QualityPanel({ snapshot, mode }: { snapshot: TickerSnapshot; mode: "put" | "call" }) {
  const { t } = useI18n();
  const ctx = snapshot.iv_context;
  const buckets = Object.values(snapshot.buckets);
  if (!ctx && buckets.length === 0) return null;
  return (
    <div className="quality-panel">
      {ctx ? (
        <>
          <p className="quality-kicker">{t("desk.qualityKicker")}</p>
          <dl className="quality-grid">
            <QualityStat label={t("desk.qualityIv")} value={pct(ctx.atm_iv)} />
            <QualityStat label={t("desk.qualityHv20")} value={pct(ctx.hv_20)} />
            <QualityStat label={t("desk.qualityHv60")} value={pct(ctx.hv_60)} />
            <QualityStat label={t("desk.qualityHv120")} value={pct(ctx.hv_120)} />
            <QualityStat
              label={t("desk.qualityRatio")}
              value={ctx.iv_hv_ratio != null ? ctx.iv_hv_ratio.toFixed(2) : t("desk.qualityNa")}
            />
            <QualityStat label={t("desk.ivRegime")} value={t(ivRegimeKey(ctx.regime))} />
          </dl>
          {ctx.expected_move_pct != null ? (
            <p className="quality-em">
              {t("desk.qualityEm")} ±{(ctx.expected_move_pct * 100).toFixed(1)}%
              {ctx.expected_move != null ? ` ($${ctx.expected_move.toFixed(2)})` : ""}
              {ctx.expected_move_dte != null
                ? ` · ${t("desk.qualityEmDte", { dte: ctx.expected_move_dte })}`
                : ""}
            </p>
          ) : null}
        </>
      ) : null}
      {ctx?.expected_move != null && ctx.expected_move > 0 ? (
        <ExpectedMoveRuler
          spot={snapshot.spot}
          expectedMove={ctx.expected_move}
          buckets={buckets}
          mode={mode}
        />
      ) : null}
    </div>
  );
}

function QualityStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="quality-stat">
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}

function ExpectedMoveRuler({
  spot,
  expectedMove,
  buckets,
  mode,
}: {
  spot: number;
  expectedMove: number;
  buckets: BucketCandidate[];
  mode: "put" | "call";
}) {
  const { t } = useI18n();
  const marks = buckets.map((bucket) => ({
    strike: bucket.csp.strike,
    name: bucket.bucket,
    inside: Boolean(bucket.score?.inside_expected_move),
  }));
  const lo = Math.min(spot - expectedMove * 1.4, ...marks.map((m) => m.strike), spot);
  const hi = Math.max(spot + expectedMove * 1.4, ...marks.map((m) => m.strike), spot);
  const span = hi - lo || 1;
  const x = (price: number) => ((price - lo) / span) * 100;
  const emLeft = x(spot - expectedMove);
  const emWidth = x(spot + expectedMove) - emLeft;
  const aria = `${t("desk.emBand")}: ${spot.toFixed(2)} ± ${expectedMove.toFixed(2)}`;

  return (
    <div className="em-ruler" role="img" aria-label={aria}>
      <div className="em-track">
        <span className="em-band" style={{ left: `${emLeft}%`, width: `${emWidth}%` }} />
        <span className="em-spot" style={{ left: `${x(spot)}%` }} />
        {marks.map((mark) => (
          <span
            key={`${mark.name}-${mark.strike}`}
            className={`em-strike ${mark.inside ? "is-inside" : ""}`}
            style={{ left: `${x(mark.strike)}%` }}
          />
        ))}
      </div>
      <p className="em-caption">
        {t("desk.emSpot")} {spot.toFixed(2)} · {t("desk.emBand")} ±{expectedMove.toFixed(2)}
      </p>
      <ul className="em-legs">
        {marks.map((mark) => (
          <li key={`${mark.name}-leg`}>
            <span className="font-[family-name:var(--font-mono)]">
              {mark.name} {mark.strike}
              {mode === "call" ? "C" : "P"}
            </span>
            <span className={mark.inside ? "text-[var(--skip)]" : "text-[var(--mute)]"}>
              {mark.inside ? t("desk.emInside") : t("desk.emOutside")}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
