import type { ExpirationPayoff } from "./types";

type Props = {
  ticker: string;
  payoff: ExpirationPayoff;
};

function money(value: number, digits = 0): string {
  const abs = Math.abs(value).toLocaleString("en-US", {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits,
  });
  return `${value < 0 ? "−" : ""}$${abs}`;
}

function signedMoney(value: number): string {
  const abs = Math.abs(value).toLocaleString("en-US", { maximumFractionDigits: 0 });
  if (value > 0) return `+$${abs}`;
  if (value < 0) return `−$${abs}`;
  return "$0";
}

function strikeLabel(value: number): string {
  return Number.isInteger(value) ? String(value) : value.toFixed(2);
}

type PlotPt = { x: number; y: number; spot: number; pnl: number };

type AxisMark = {
  key: string;
  spot: number;
  label: string;
  tone: "be" | "strike";
};

export function PayoffChart({ ticker, payoff }: Props) {
  const width = 640;
  const height = 248;
  const pad = { l: 58, r: 14, t: 22, b: 38 };
  const innerW = width - pad.l - pad.r;
  const innerH = height - pad.t - pad.b;
  const xMin = payoff.x_min;
  const xMax = payoff.x_max;
  const pnls = payoff.points.map((p) => p.pnl);
  const yPad = Math.max((Math.max(0, ...pnls) - Math.min(0, ...pnls)) * 0.12, 40);
  const yMin = Math.min(0, ...pnls) - yPad;
  const yMax = Math.max(0, ...pnls) + yPad;
  const uid = `po-${ticker.replace(/[^A-Za-z0-9]/g, "")}`;

  const xPx = (spot: number) => pad.l + ((spot - xMin) / (xMax - xMin || 1)) * innerW;
  const yPx = (pnl: number) => pad.t + ((yMax - pnl) / (yMax - yMin || 1)) * innerH;
  const zeroY = yPx(0);

  const pts: PlotPt[] = payoff.points.map((p) => ({
    x: xPx(p.spot),
    y: yPx(p.pnl),
    spot: p.spot,
    pnl: p.pnl,
  }));
  const line = pts.map((p, i) => `${i === 0 ? "M" : "L"} ${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(" ");
  const area =
    pts.length >= 2
      ? `M ${pts[0].x.toFixed(1)} ${zeroY.toFixed(1)} ${pts
          .map((p) => `L ${p.x.toFixed(1)} ${p.y.toFixed(1)}`)
          .join(" ")} L ${pts[pts.length - 1].x.toFixed(1)} ${zeroY.toFixed(1)} Z`
      : "";

  const marks = placeMarks(payoff, xPx);
  const expiry = payoff.expiry.slice(0, 10);
  const structure =
    payoff.structure === "BULL_PUT_SPREAD"
      ? "牛市看跌价差"
      : payoff.structure === "COVERED_CALL"
        ? "Covered Call"
        : "CSP";
  const lossText = payoff.loss_limited ? money(payoff.max_loss) : `${money(payoff.max_loss)} · 到 $0`;
  const spotX = xPx(payoff.spot);
  const spotTagRight = spotX > pad.l + innerW * 0.62;
  const floorPnl = Math.min(...pnls);
  const showMaxY = Math.abs(yPx(payoff.max_profit) - zeroY) > 16;
  const showFloorY = Math.abs(yPx(floorPnl) - zeroY) > 16;

  return (
    <div className="payoff-tape">
      <p className="payoff-kicker">
        到期结算 {expiry} · {payoff.dte}DTE · {payoff.contracts} 张 · {structure}
      </p>
      <dl className="payoff-stats">
        <div>
          <dt>最大盈利</dt>
          <dd className="text-[var(--open)]">{money(payoff.max_profit)}</dd>
        </div>
        <div>
          <dt>盈亏平衡</dt>
          <dd>{strikeLabel(payoff.breakeven)}</dd>
        </div>
        <div>
          <dt>最大亏损</dt>
          <dd className="text-[var(--skip)]">{lossText}</dd>
        </div>
        <div>
          <dt>净权利金 / 张</dt>
          <dd>{money(payoff.credit_per_share * 100)}</dd>
        </div>
      </dl>
      <svg
        className="payoff-plot"
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-label={`${ticker} ${structure}到期损益图，盈亏平衡 ${strikeLabel(payoff.breakeven)}`}
      >
        <defs>
          <clipPath id={`${uid}-up`}>
            <rect x={pad.l} y={pad.t} width={innerW} height={Math.max(0, zeroY - pad.t)} />
          </clipPath>
          <clipPath id={`${uid}-dn`}>
            <rect x={pad.l} y={zeroY} width={innerW} height={Math.max(0, pad.t + innerH - zeroY)} />
          </clipPath>
        </defs>
        <rect x={pad.l} y={pad.t} width={innerW} height={innerH} className="payoff-well" />
        <line
          x1={pad.l}
          x2={pad.l + innerW}
          y1={zeroY}
          y2={zeroY}
          className="payoff-zero"
        />
        {area ? (
          <>
            <path d={area} clipPath={`url(#${uid}-up)`} className="payoff-fill-up" />
            <path d={area} clipPath={`url(#${uid}-dn)`} className="payoff-fill-dn" />
          </>
        ) : null}
        <path d={line} className="payoff-line" />
        <line
          x1={xPx(payoff.spot)}
          x2={xPx(payoff.spot)}
          y1={pad.t}
          y2={pad.t + innerH}
          className="payoff-spot"
        />
        {marks.map((mark) => (
          <g key={mark.key}>
            <line
              x1={mark.x}
              x2={mark.x}
              y1={pad.t + innerH}
              y2={pad.t + innerH + 5}
              className="payoff-tick"
            />
            <text
              x={mark.x}
              y={height - 8}
              textAnchor="middle"
              className={`payoff-xlabel payoff-xlabel-${mark.tone}`}
            >
              {mark.label}
            </text>
          </g>
        ))}
        {showMaxY ? (
          <text x={pad.l - 8} y={yPx(payoff.max_profit) + 4} textAnchor="end" className="payoff-ylabel">
            {signedMoney(payoff.max_profit)}
          </text>
        ) : null}
        <text x={pad.l - 8} y={zeroY + 4} textAnchor="end" className="payoff-ylabel">
          $0
        </text>
        {showFloorY ? (
          <text x={pad.l - 8} y={yPx(floorPnl) + 4} textAnchor="end" className="payoff-ylabel">
            {signedMoney(floorPnl)}
          </text>
        ) : null}
        <text
          x={spotTagRight ? spotX - 6 : spotX + 6}
          y={pad.t + 12}
          textAnchor={spotTagRight ? "end" : "start"}
          className="payoff-spot-tag"
        >
          现价 {strikeLabel(payoff.spot)}
        </text>
      </svg>
      <p className="payoff-foot">
        到期若仍在现价：{signedMoney(payoff.pnl_at_spot)}
        {payoff.structure === "COVERED_CALL"
          ? payoff.assignment_cash != null
            ? ` · 若指派按行权价卖出，收入 ${money(payoff.assignment_cash)}`
            : ""
          : payoff.assignment_cash != null
            ? ` · 若指派需现金 ${money(payoff.assignment_cash)}`
            : ""}
        {payoff.cost_basis != null ? ` · 成本 ${money(payoff.cost_basis, 2)}` : ""}
        。按链上 mid 估算，非成交价；不含手续费与提前指派。
      </p>
    </div>
  );
}

function placeMarks(
  payoff: ExpirationPayoff,
  xPx: (spot: number) => number,
): Array<AxisMark & { x: number }> {
  const raw: AxisMark[] = [
    { key: "be", spot: payoff.breakeven, label: `BE ${strikeLabel(payoff.breakeven)}`, tone: "be" },
    { key: "ks", spot: payoff.short_strike, label: `K ${strikeLabel(payoff.short_strike)}`, tone: "strike" },
  ];
  if (payoff.long_strike != null) {
    raw.push({
      key: "kl",
      spot: payoff.long_strike,
      label: `保护 ${strikeLabel(payoff.long_strike)}`,
      tone: "strike",
    });
  }
  const kept: Array<AxisMark & { x: number }> = [];
  for (const mark of raw) {
    if (mark.spot < payoff.x_min || mark.spot > payoff.x_max) continue;
    const x = xPx(mark.spot);
    if (kept.some((prev) => Math.abs(prev.x - x) < 44)) continue;
    kept.push({ ...mark, x });
  }
  return kept;
}
