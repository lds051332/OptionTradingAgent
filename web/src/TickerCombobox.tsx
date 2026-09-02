import {
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent,
} from "react";

export type Underlying = {
  symbol: string;
  name: string;
};

/** Options-volume / retail-heat leaders among US stocks and ETFs. */
export const HOT_UNDERLYINGS: Underlying[] = [
  { symbol: "SPY", name: "标普 500 ETF" },
  { symbol: "QQQ", name: "纳指 100 ETF" },
  { symbol: "NVDA", name: "英伟达" },
  { symbol: "TSLA", name: "特斯拉" },
  { symbol: "AAPL", name: "苹果" },
  { symbol: "AMZN", name: "亚马逊" },
  { symbol: "MSFT", name: "微软" },
  { symbol: "META", name: "Meta" },
  { symbol: "AMD", name: "超微" },
  { symbol: "IWM", name: "罗素 2000 ETF" },
  { symbol: "GOOGL", name: "谷歌" },
  { symbol: "NFLX", name: "奈飞" },
  { symbol: "AVGO", name: "博通" },
  { symbol: "PLTR", name: "Palantir" },
  { symbol: "TQQQ", name: "三倍做多纳指" },
  { symbol: "IBIT", name: "比特币现货 ETF" },
  { symbol: "COIN", name: "Coinbase" },
  { symbol: "SOXL", name: "三倍做多半导体" },
  { symbol: "MSTR", name: "Strategy" },
  { symbol: "HOOD", name: "Robinhood" },
];

const RANK = new Map(HOT_UNDERLYINGS.map((item, index) => [item.symbol, index + 1]));

export function normalizeSymbol(raw: string): string {
  return raw.trim().toUpperCase().replace(/[^A-Z.]/g, "");
}

type Props = {
  id?: string;
  value: string;
  onChange: (symbol: string) => void;
};

type Row = Underlying & { rank: number; custom?: boolean };

export function TickerCombobox({ id, value, onChange }: Props) {
  const listId = useId();
  const rootRef = useRef<HTMLDivElement>(null);
  const listRef = useRef<HTMLUListElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState(value);
  const [filtering, setFiltering] = useState(false);
  const [active, setActive] = useState(0);

  const rows = useMemo<Row[]>(() => {
    const typed = normalizeSymbol(query);
    const nameQ = query.trim().toLowerCase();
    const pool = filtering
      ? HOT_UNDERLYINGS.filter((item) => {
          const symbolHit = typed.length > 0 && item.symbol.includes(typed);
          const nameHit = nameQ.length > 0 && item.name.toLowerCase().includes(nameQ);
          return symbolHit || nameHit;
        })
      : HOT_UNDERLYINGS;
    const mapped: Row[] = pool.map((item) => ({
      ...item,
      rank: RANK.get(item.symbol) ?? 0,
    }));
    const known = HOT_UNDERLYINGS.some((item) => item.symbol === typed);
    if (typed && !known) {
      return [{ symbol: typed, name: "使用该代码", rank: 0, custom: true }, ...mapped];
    }
    return mapped;
  }, [filtering, query]);

  useEffect(() => {
    if (!open) setQuery(value);
  }, [open, value]);

  useEffect(() => {
    if (!open) return;
    function onPointerDown(event: PointerEvent) {
      if (!rootRef.current?.contains(event.target as Node)) {
        commit(query);
        setOpen(false);
      }
    }
    document.addEventListener("pointerdown", onPointerDown);
    return () => document.removeEventListener("pointerdown", onPointerDown);
  }, [open, query]);

  useEffect(() => {
    if (!open) return;
    const node = listRef.current?.querySelector<HTMLElement>("[data-active='true']");
    node?.scrollIntoView({ block: "nearest" });
  }, [active, open, rows]);

  function commit(raw: string): string {
    const symbol = normalizeSymbol(raw) || value;
    onChange(symbol);
    setQuery(symbol);
    setFiltering(false);
    return symbol;
  }

  function openMenu() {
    const idx = HOT_UNDERLYINGS.findIndex((item) => item.symbol === value);
    setQuery(value);
    setFiltering(false);
    setActive(Math.max(idx, 0));
    setOpen(true);
  }

  function pick(row: Row) {
    commit(row.symbol);
    setOpen(false);
  }

  function onKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      if (!open) {
        openMenu();
        return;
      }
      setActive((current) => Math.min(current + 1, Math.max(rows.length - 1, 0)));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      if (!open) {
        openMenu();
        return;
      }
      setActive((current) => Math.max(current - 1, 0));
    } else if (event.key === "Enter" && open) {
      event.preventDefault();
      const row = rows[active];
      if (row) pick(row);
      else commit(query);
    } else if (event.key === "Escape") {
      event.preventDefault();
      setQuery(value);
      setFiltering(false);
      setOpen(false);
    } else if (event.key === "Tab") {
      commit(query);
      setOpen(false);
    }
  }

  const activeId = rows[active] ? `${listId}-${rows[active].symbol}` : undefined;

  return (
    <div ref={rootRef} className="relative mt-2">
      <div
        className={`flex min-h-11 items-stretch rounded-sm border bg-[var(--night)] ${
          open ? "border-[var(--brass)]" : "border-[var(--hairline)]"
        }`}
      >
        <input
          ref={inputRef}
          id={id}
          name="ticker"
          role="combobox"
          aria-expanded={open}
          aria-controls={listId}
          aria-activedescendant={open ? activeId : undefined}
          aria-autocomplete="list"
          autoComplete="off"
          autoCapitalize="characters"
          spellCheck={false}
          value={query}
          placeholder="输入或选择，如 NVDA"
          onChange={(event) => {
            const next = event.target.value;
            setQuery(next);
            setFiltering(true);
            setActive(0);
            if (!open) setOpen(true);
          }}
          onFocus={() => {
            if (!open) openMenu();
            requestAnimationFrame(() => inputRef.current?.select());
          }}
          onKeyDown={onKeyDown}
          className="min-h-11 min-w-0 flex-1 bg-transparent px-3 font-[family-name:var(--font-mono)] text-sm tracking-wide text-[var(--brass)] outline-none focus-visible:outline-none"
        />
        <button
          type="button"
          tabIndex={-1}
          aria-label={open ? "收起标的列表" : "打开标的列表"}
          onClick={() => {
            if (open) {
              commit(query);
              setOpen(false);
            } else {
              inputRef.current?.focus();
            }
          }}
          className="flex w-11 items-center justify-center text-[var(--mute)]"
        >
          <svg viewBox="0 0 12 8" width="12" height="8" aria-hidden className={open ? "rotate-180" : ""}>
            <path d="M1 1.5 L6 6.5 L11 1.5" fill="none" stroke="currentColor" strokeWidth="1.5" />
          </svg>
        </button>
      </div>
      {open ? (
        <ul
          ref={listRef}
          id={listId}
          role="listbox"
          className="ticker-menu absolute z-20 mt-1 max-h-[min(18rem,50dvh)] w-full overflow-y-auto border border-[var(--hairline)] bg-[var(--blotter)] py-1 shadow-[0_16px_40px_rgba(0,0,0,0.35)]"
        >
          {rows.length === 0 ? (
            <li className="px-3 py-3 text-sm text-[var(--mute)]">没有匹配，继续输入自定义代码</li>
          ) : (
            rows.map((row, index) => {
              const selected = row.symbol === value && !row.custom;
              const isActive = index === active;
              return (
                <li
                  key={`${row.custom ? "custom" : "hot"}-${row.symbol}`}
                  id={`${listId}-${row.symbol}`}
                  role="option"
                  aria-selected={selected}
                  data-active={isActive ? "true" : "false"}
                  onMouseEnter={() => setActive(index)}
                  onMouseDown={(event) => event.preventDefault()}
                  onClick={() => pick(row)}
                  className={`flex min-h-11 cursor-pointer items-center gap-3 px-3 ${
                    isActive ? "bg-[var(--card)]" : ""
                  }`}
                >
                  <span className="w-6 shrink-0 font-[family-name:var(--font-mono)] text-[11px] tabular-nums text-[var(--mute)]">
                    {row.custom ? "↩" : String(row.rank).padStart(2, "0")}
                  </span>
                  <span className="w-16 shrink-0 font-[family-name:var(--font-mono)] text-sm tracking-wide text-[var(--brass)]">
                    {row.symbol}
                  </span>
                  <span className="min-w-0 truncate text-sm text-[var(--mute)]">{row.name}</span>
                  {selected ? (
                    <span className="ml-auto font-[family-name:var(--font-mono)] text-[11px] text-[var(--brass)]">
                      当前
                    </span>
                  ) : null}
                </li>
              );
            })
          )}
        </ul>
      ) : null}
    </div>
  );
}
