import { realizedOptionPnl } from "./calculations";
import { parseJsonOrThrow, POSITIONS_KEY, readStorageRaw, StorageError, writeStorageRaw } from "./storage";
import type { Position, PositionDraft } from "./types";
import { parsePositionList } from "./validate";

function newId(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `pos_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 10)}`;
}

function persist(positions: Position[]): Position[] {
  writeStorageRaw(POSITIONS_KEY, JSON.stringify(positions));
  return positions;
}

export function loadPositions(): Position[] {
  const raw = readStorageRaw(POSITIONS_KEY);
  if (!raw) return [];
  const parsed = parsePositionList(parseJsonOrThrow(raw));
  if (!parsed) throw new StorageError();
  return parsed;
}

export function replacePositions(positions: Position[]): Position[] {
  return persist(positions);
}

export function addPosition(draft: PositionDraft): Position {
  const positions = loadPositions();
  const position: Position = {
    id: newId(),
    ticker: draft.ticker.trim().toUpperCase(),
    strategy: draft.strategy,
    optionType: draft.optionType,
    expiry: draft.expiry,
    strike: draft.strike,
    contracts: Math.round(draft.contracts),
    entryPremium: draft.entryPremium,
    openedAt: draft.openedAt || new Date().toISOString(),
    status: "OPEN",
    assignmentOk: draft.assignmentOk,
    shares: draft.strategy === "COVERED_CALL" ? draft.shares : undefined,
    costBasis: draft.strategy === "COVERED_CALL" ? draft.costBasis : undefined,
    note: draft.note?.trim() || undefined,
  };
  positions.push(position);
  persist(positions);
  return position;
}

export function updatePosition(id: string, patch: Partial<Position>): Position {
  const positions = loadPositions();
  const index = positions.findIndex((item) => item.id === id);
  if (index < 0) throw new Error("position_missing");
  const next = { ...positions[index], ...patch, id };
  positions[index] = next;
  persist(positions);
  return next;
}

export function deletePosition(id: string): void {
  persist(loadPositions().filter((item) => item.id !== id));
}

export function closePosition(
  id: string,
  input: { closePrice: number; fees?: number; closedAt?: string },
): Position {
  const current = loadPositions().find((item) => item.id === id);
  if (!current) throw new Error("position_missing");
  const fees = input.fees ?? 0;
  return updatePosition(id, {
    status: "CLOSED",
    closePrice: input.closePrice,
    closeFees: fees,
    closedAt: input.closedAt || new Date().toISOString(),
    realizedPnl: realizedOptionPnl(current.entryPremium, input.closePrice, current.contracts, fees),
  });
}

export function rollPosition(
  id: string,
  input: {
    closePrice: number;
    newPremium: number;
    newExpiry: string;
    newStrike: number;
    fees?: number;
    contracts?: number;
  },
): { old: Position; next: Position } {
  const current = loadPositions().find((item) => item.id === id);
  if (!current) throw new Error("position_missing");
  const fees = input.fees ?? 0;
  const nextDraft: PositionDraft = {
    ticker: current.ticker,
    strategy: current.strategy,
    optionType: current.optionType,
    expiry: input.newExpiry,
    strike: input.newStrike,
    contracts: input.contracts ?? current.contracts,
    entryPremium: input.newPremium,
    assignmentOk: current.assignmentOk,
    shares: current.shares,
    costBasis: current.costBasis,
    note: current.note,
  };
  const next = addPosition(nextDraft);
  const old = updatePosition(id, {
    status: "ROLLED",
    closePrice: input.closePrice,
    closeFees: fees,
    closedAt: new Date().toISOString(),
    realizedPnl: realizedOptionPnl(current.entryPremium, input.closePrice, current.contracts, fees),
    rolledToPositionId: next.id,
  });
  const linked = updatePosition(next.id, { rolledFromPositionId: old.id });
  return { old, next: linked };
}

export function openPositions(positions: Position[]): Position[] {
  return positions.filter((item) => item.status === "OPEN");
}

export function historyPositions(positions: Position[]): Position[] {
  return positions
    .filter((item) => item.status !== "OPEN")
    .sort((a, b) => (b.closedAt || b.openedAt).localeCompare(a.closedAt || a.openedAt));
}
