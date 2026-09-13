import type { TickerDecision } from "../types";
import type { PositionDraft } from "./types";

export function draftFromOpenDecision(input: {
  decision: TickerDecision;
  shares?: number;
  costBasis?: number;
}): PositionDraft | null {
  const { decision } = input;
  if (decision.action !== "OPEN") return null;
  if (decision.structure === "BULL_PUT_SPREAD") return null;
  if (decision.structure !== "CSP" && decision.structure !== "COVERED_CALL") return null;
  const payoff = decision.payoff;
  if (!payoff) return null;
  const strategy = decision.structure;
  return {
    ticker: decision.ticker,
    strategy,
    optionType: strategy === "COVERED_CALL" ? "CALL" : "PUT",
    expiry: payoff.expiry,
    strike: payoff.short_strike,
    contracts: payoff.contracts,
    entryPremium: payoff.credit_per_share,
    assignmentOk: decision.assignment_ok,
    openedAt: new Date().toISOString(),
    shares: strategy === "COVERED_CALL" ? input.shares : undefined,
    costBasis: strategy === "COVERED_CALL" ? (input.costBasis || payoff.cost_basis || undefined) : undefined,
    fromRecommendation: true,
  };
}
