import type { PositionDraft } from "./types";
import { parseJsonOrThrow, POSITION_DRAFT_KEY, readStorageRaw, removeStorageRaw, writeStorageRaw } from "./storage";

export function saveDraft(draft: PositionDraft): void {
  writeStorageRaw(POSITION_DRAFT_KEY, JSON.stringify(draft));
}

export function clearDraft(): void {
  removeStorageRaw(POSITION_DRAFT_KEY);
}

export function readDraft(): PositionDraft | null {
  try {
    const raw = readStorageRaw(POSITION_DRAFT_KEY);
    if (!raw) return null;
    const parsed = parseJsonOrThrow(raw);
    if (!parsed || typeof parsed !== "object") return null;
    return parsed as PositionDraft;
  } catch {
    return null;
  }
}
