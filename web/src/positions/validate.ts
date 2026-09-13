import type { Position, PositionOptionType, PositionStatus, PositionStrategy } from "./types";

const STRATEGIES = new Set<PositionStrategy>(["CSP", "COVERED_CALL"]);
const STATUSES = new Set<PositionStatus>(["OPEN", "CLOSED", "ROLLED"]);
const OPTION_TYPES = new Set<PositionOptionType>(["PUT", "CALL"]);

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function isFiniteNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function optionalNumber(value: unknown): number | undefined {
  if (value === undefined || value === null) return undefined;
  return isFiniteNumber(value) ? value : undefined;
}

function optionalString(value: unknown): string | undefined {
  if (value === undefined || value === null) return undefined;
  return typeof value === "string" ? value : undefined;
}

export function parsePosition(value: unknown): Position | null {
  if (!isRecord(value)) return null;
  if (typeof value.id !== "string" || !value.id.trim()) return null;
  if (typeof value.ticker !== "string" || !value.ticker.trim()) return null;
  if (typeof value.strategy !== "string" || !STRATEGIES.has(value.strategy as PositionStrategy)) return null;
  if (typeof value.optionType !== "string" || !OPTION_TYPES.has(value.optionType as PositionOptionType)) return null;
  if (typeof value.expiry !== "string" || !/^\d{4}-\d{2}-\d{2}$/.test(value.expiry)) return null;
  if (!isFiniteNumber(value.strike) || value.strike <= 0) return null;
  if (!isFiniteNumber(value.contracts) || value.contracts < 1) return null;
  if (!isFiniteNumber(value.entryPremium) || value.entryPremium < 0) return null;
  if (typeof value.openedAt !== "string" || !value.openedAt) return null;
  if (typeof value.status !== "string" || !STATUSES.has(value.status as PositionStatus)) return null;
  if (typeof value.assignmentOk !== "boolean") return null;

  const strategy = value.strategy as PositionStrategy;
  const optionType = value.optionType as PositionOptionType;
  if (strategy === "CSP" && optionType !== "PUT") return null;
  if (strategy === "COVERED_CALL" && optionType !== "CALL") return null;

  const shares = optionalNumber(value.shares);
  const costBasis = optionalNumber(value.costBasis);
  if (strategy === "COVERED_CALL") {
    if (shares === undefined || shares < 100) return null;
    if (costBasis === undefined || costBasis <= 0) return null;
  }

  return {
    id: value.id.trim(),
    ticker: value.ticker.trim().toUpperCase(),
    strategy,
    optionType,
    expiry: value.expiry,
    strike: value.strike,
    contracts: Math.round(value.contracts),
    entryPremium: value.entryPremium,
    openedAt: value.openedAt,
    status: value.status as PositionStatus,
    assignmentOk: value.assignmentOk,
    shares,
    costBasis,
    closedAt: optionalString(value.closedAt),
    closePrice: optionalNumber(value.closePrice),
    closeFees: optionalNumber(value.closeFees),
    realizedPnl: optionalNumber(value.realizedPnl),
    rolledFromPositionId: optionalString(value.rolledFromPositionId),
    rolledToPositionId: optionalString(value.rolledToPositionId),
    note: optionalString(value.note),
  };
}

export function parsePositionList(value: unknown): Position[] | null {
  if (!Array.isArray(value)) return null;
  const positions: Position[] = [];
  for (const item of value) {
    const parsed = parsePosition(item);
    if (!parsed) return null;
    positions.push(parsed);
  }
  return positions;
}
