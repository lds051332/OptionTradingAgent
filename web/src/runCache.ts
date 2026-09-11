import type { TimelineStep } from "./types";

export type CachedRun = {
  v: 2;
  language: string;
  mode: "put" | "call";
  ticker: string;
  delta: number;
  cash: number;
  shares: number;
  costBasis: number;
  userPrompt: string | null;
  steps: TimelineStep[];
  error: string | null;
  savedAt: string;
};

const VERSION = 2 as const;

function storageKey(mode: "put" | "call", language: string): string {
  return `option-desk:last-run:v${VERSION}:${mode}:${language}`;
}

function isStep(value: unknown): value is TimelineStep {
  if (!value || typeof value !== "object") return false;
  const step = value as TimelineStep;
  return (
    typeof step.id === "string" &&
    typeof step.type === "string" &&
    (step.status === "running" || step.status === "done" || step.status === "error") &&
    typeof step.message === "string"
  );
}

function parse(raw: string): CachedRun | null {
  try {
    const data = JSON.parse(raw) as Partial<CachedRun>;
    if (data.v !== VERSION) return null;
    if (data.mode !== "put" && data.mode !== "call") return null;
    if (typeof data.language !== "string") return null;
    if (typeof data.ticker !== "string" || typeof data.delta !== "number") return null;
    if (typeof data.cash !== "number" || typeof data.shares !== "number") return null;
    if (typeof data.costBasis !== "number" || typeof data.savedAt !== "string") return null;
    if (!Array.isArray(data.steps) || !data.steps.every(isStep)) return null;
    const steps = data.steps.filter((step) => step.status !== "running");
    if (steps.length === 0) return null;
    return {
      v: VERSION,
      language: data.language,
      mode: data.mode,
      ticker: data.ticker,
      delta: data.delta,
      cash: data.cash,
      shares: data.shares,
      costBasis: data.costBasis,
      userPrompt: typeof data.userPrompt === "string" ? data.userPrompt : null,
      steps,
      error: typeof data.error === "string" ? data.error : null,
      savedAt: data.savedAt,
    };
  } catch {
    return null;
  }
}

export function loadCachedRun(mode: "put" | "call", language: string): CachedRun | null {
  try {
    const raw = window.localStorage.getItem(storageKey(mode, language));
    if (!raw) return null;
    return parse(raw);
  } catch {
    return null;
  }
}

export function saveCachedRun(run: Omit<CachedRun, "v" | "savedAt">): CachedRun | null {
  const payload: CachedRun = {
    ...run,
    v: VERSION,
    steps: run.steps.filter((step) => step.status !== "running"),
    savedAt: new Date().toISOString(),
  };
  if (payload.steps.length === 0) return null;
  try {
    window.localStorage.setItem(storageKey(run.mode, run.language), JSON.stringify(payload));
    return payload;
  } catch {
    return null;
  }
}

export function formatCachedAt(iso: string, locale: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleString(locale, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}
