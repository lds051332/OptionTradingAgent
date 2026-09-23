import type { Defaults, StreamEvent } from "./types";
import { getLang, tx } from "./i18n";
import type {
  EvaluateResponse,
  Position,
  PositionSettings,
  RollCandidatesResponse,
} from "./positions/types";

function langHeaders(extra?: Record<string, string>): Record<string, string> {
  const lang = getLang();
  return {
    "X-Option-Desk-Lang": lang,
    "Accept-Language": lang === "zh" ? "zh-CN" : "en",
    ...extra,
  };
}

async function readJson<T>(res: Response): Promise<T> {
  const payload = (await res.json().catch(() => ({}))) as { detail?: string | unknown };
  if (!res.ok) {
    const detail = payload.detail;
    const message =
      typeof detail === "string"
        ? detail
        : Array.isArray(detail)
          ? detail.map((item) => String((item as { msg?: string }).msg ?? item)).join("；")
          : tx("api.requestFailed", { status: res.status });
    throw new Error(message);
  }
  return payload as T;
}

export async function fetchMe(): Promise<Defaults> {
  const res = await fetch("/api/me", { credentials: "include", headers: langHeaders() });
  return readJson<Defaults>(res);
}

export type DemoSummary = {
  id: string;
  kicker: string;
  title: string;
  summary: string;
};

export async function fetchDemos(): Promise<DemoSummary[]> {
  const res = await fetch("/api/demos", { credentials: "include", headers: langHeaders() });
  const body = await readJson<{ scenarios: DemoSummary[] }>(res);
  return body.scenarios;
}

async function* readEventStream(res: Response): AsyncGenerator<StreamEvent> {
  if (!res.ok) {
    await readJson(res);
    return;
  }
  if (!res.body) throw new Error(tx("api.noStream"));

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let eventName = "message";
  let dataLines: string[] = [];

  const flush = (): StreamEvent | null => {
    if (dataLines.length === 0) return null;
    const raw = dataLines.join("\n");
    dataLines = [];
    const name = eventName;
    eventName = "message";
    const parsed = JSON.parse(raw) as StreamEvent;
    if (!parsed.type) parsed.type = name;
    return parsed;
  };

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let newline = buffer.indexOf("\n");
    while (newline >= 0) {
      let line = buffer.slice(0, newline);
      buffer = buffer.slice(newline + 1);
      if (line.endsWith("\r")) line = line.slice(0, -1);
      if (line === "") {
        const item = flush();
        if (item) yield item;
      } else if (line.startsWith("event:")) {
        eventName = line.slice(6).trim();
      } else if (line.startsWith("data:")) {
        dataLines.push(line.slice(5).trimStart());
      }
      newline = buffer.indexOf("\n");
    }
  }
  const tail = flush();
  if (tail) yield tail;
}

export async function* startReplay(
  scenario: string,
  options?: { signal?: AbortSignal },
): AsyncGenerator<StreamEvent> {
  const res = await fetch(`/api/demos/${encodeURIComponent(scenario)}`, {
    method: "POST",
    credentials: "include",
    headers: langHeaders({ Accept: "text/event-stream" }),
    signal: options?.signal,
  });
  yield* readEventStream(res);
}

export async function* startRun(
  body: {
    tickers: string[];
    delta: number;
    cash?: number;
    mode?: "put" | "call";
    shares?: number;
    cost_basis?: number;
    language?: string;
  },
  options?: { signal?: AbortSignal },
): AsyncGenerator<StreamEvent> {
  const res = await fetch("/api/runs", {
    method: "POST",
    credentials: "include",
    headers: langHeaders({ "Content-Type": "application/json", Accept: "text/event-stream" }),
    body: JSON.stringify({ ...body, language: body.language ?? getLang() }),
    signal: options?.signal,
  });
  yield* readEventStream(res);
}

export async function evaluatePositions(
  positions: Position[],
  settings: PositionSettings,
  options?: { signal?: AbortSignal },
): Promise<EvaluateResponse> {
  const res = await fetch("/api/positions/evaluate", {
    method: "POST",
    credentials: "include",
    headers: langHeaders({ "Content-Type": "application/json" }),
    signal: options?.signal,
    body: JSON.stringify({
      settings: {
        profitTarget: settings.profitTarget,
        nearExpiryDte: settings.nearExpiryDte,
        nearExpiryProfitTarget: settings.nearExpiryProfitTarget,
      },
      positions: positions.map((item) => ({
        id: item.id,
        ticker: item.ticker,
        strategy: item.strategy,
        optionType: item.optionType,
        expiry: item.expiry,
        strike: item.strike,
        contracts: item.contracts,
        entryPremium: item.entryPremium,
        assignmentOk: item.assignmentOk,
      })),
    }),
  });
  return readJson<EvaluateResponse>(res);
}

export async function fetchRollCandidates(
  position: Position,
  estimatedClosePrice: number | null,
  targetDelta?: number,
  options?: { signal?: AbortSignal },
): Promise<RollCandidatesResponse> {
  const res = await fetch("/api/positions/roll-candidates", {
    method: "POST",
    credentials: "include",
    headers: langHeaders({ "Content-Type": "application/json" }),
    signal: options?.signal,
    body: JSON.stringify({
      ticker: position.ticker,
      optionType: position.optionType,
      expiry: position.expiry,
      strike: position.strike,
      contracts: position.contracts,
      estimatedClosePrice,
      targetDelta,
    }),
  });
  return readJson<RollCandidatesResponse>(res);
}
