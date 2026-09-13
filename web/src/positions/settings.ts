import type { PositionSettings } from "./types";
import { parseJsonOrThrow, POSITION_SETTINGS_KEY, readStorageRaw, writeStorageRaw } from "./storage";

export const DEFAULT_POSITION_SETTINGS: PositionSettings = {
  profitTarget: 0.75,
  nearExpiryDte: 2,
  nearExpiryProfitTarget: 0.5,
};

function isFiniteNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

export function parsePositionSettings(value: unknown): PositionSettings | null {
  if (!value || typeof value !== "object") return null;
  const row = value as Record<string, unknown>;
  const profitTarget = isFiniteNumber(row.profitTarget) ? row.profitTarget : DEFAULT_POSITION_SETTINGS.profitTarget;
  const nearExpiryDte = isFiniteNumber(row.nearExpiryDte)
    ? Math.round(row.nearExpiryDte)
    : DEFAULT_POSITION_SETTINGS.nearExpiryDte;
  const nearExpiryProfitTarget = isFiniteNumber(row.nearExpiryProfitTarget)
    ? row.nearExpiryProfitTarget
    : DEFAULT_POSITION_SETTINGS.nearExpiryProfitTarget;
  if (profitTarget <= 0 || profitTarget > 1) return null;
  if (nearExpiryDte < 0 || nearExpiryDte > 14) return null;
  if (nearExpiryProfitTarget <= 0 || nearExpiryProfitTarget > 1) return null;
  return { profitTarget, nearExpiryDte, nearExpiryProfitTarget };
}

export function loadPositionSettings(): PositionSettings {
  const raw = readStorageRaw(POSITION_SETTINGS_KEY);
  if (!raw) return { ...DEFAULT_POSITION_SETTINGS };
  const parsed = parsePositionSettings(parseJsonOrThrow(raw));
  return parsed ?? { ...DEFAULT_POSITION_SETTINGS };
}

export function savePositionSettings(settings: PositionSettings): PositionSettings {
  const parsed = parsePositionSettings(settings) ?? DEFAULT_POSITION_SETTINGS;
  writeStorageRaw(POSITION_SETTINGS_KEY, JSON.stringify(parsed));
  return parsed;
}
