import { replacePositions } from "./repository";
import { parsePosition, parsePositionList } from "./validate";
import type { Position, PositionsExport } from "./types";

const SCHEMA_VERSION = 1 as const;

export function buildExportPayload(positions: Position[]): PositionsExport {
  return {
    schemaVersion: SCHEMA_VERSION,
    exportedAt: new Date().toISOString(),
    positions,
  };
}

export function exportFileName(when = new Date()): string {
  const stamp = when.toISOString().slice(0, 10);
  return `option-desk-positions-${stamp}.json`;
}

export function parseImportPayload(value: unknown): Position[] {
  if (!value || typeof value !== "object") {
    throw new Error("import_invalid");
  }
  const row = value as Record<string, unknown>;
  if (row.schemaVersion !== SCHEMA_VERSION) {
    throw new Error("import_invalid");
  }
  const parsed = parsePositionList(row.positions);
  if (!parsed) {
    throw new Error("import_invalid");
  }
  return parsed;
}

export function mergePositions(existing: Position[], incoming: Position[]): Position[] {
  const byId = new Map(existing.map((item) => [item.id, item]));
  for (const item of incoming) {
    const parsed = parsePosition(item);
    if (!parsed) throw new Error("import_invalid");
    byId.set(parsed.id, parsed);
  }
  return [...byId.values()];
}

export function applyImport(
  existing: Position[],
  incoming: Position[],
  mode: "replace" | "merge",
): Position[] {
  const next = mode === "replace" ? incoming : mergePositions(existing, incoming);
  return replacePositions(next);
}

export function downloadPositionsJson(positions: Position[]): void {
  const payload = buildExportPayload(positions);
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = exportFileName();
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}
