import { BrandLockup } from "./Brand";

type DeskMode = "put" | "call";

type Props = {
  onOpen: (mode: DeskMode) => void;
  onLogout: () => void;
};

export function Home({ onOpen, onLogout }: Props) {
  return (
    <div className="mx-auto flex min-h-dvh max-w-2xl flex-col px-4 pb-[max(1.5rem,env(safe-area-inset-bottom))] pt-[max(1rem,env(safe-area-inset-top))]">
      <header className="mb-8 flex items-center justify-between gap-3">
        <BrandLockup title="本周两本账" />
        <button type="button" onClick={onLogout} className="min-h-11 px-2 text-sm text-[var(--mute)]">
          退出
        </button>
      </header>

      <p className="mb-6 max-w-md text-sm leading-relaxed text-[var(--mute)]">
        现金一边卖 put，被指派后翻到对面卖 call。先选你现在站在哪一侧。
      </p>

      <div className="flex flex-col gap-4">
        <GateCard
          index="01"
          kicker="Cash book"
          title="持币卖 Put"
          body="现金担保。CSP 或牛市看跌价差。被指派后再换到持股账。"
          action="打开卖 Put 决策台"
          tone="cash"
          onClick={() => onOpen("put")}
        />
        <GateCard
          index="02"
          kicker="Stock book"
          title="持股卖 Call"
          body="手里已经有股票。只卖 covered call，到期要么收租，要么按行权价卖掉。"
          action="打开卖 Call 决策台"
          tone="stock"
          onClick={() => onOpen("call")}
        />
      </div>
    </div>
  );
}

function GateCard({
  index,
  kicker,
  title,
  body,
  action,
  tone,
  onClick,
}: {
  index: string;
  kicker: string;
  title: string;
  body: string;
  action: string;
  tone: "cash" | "stock";
  onClick: () => void;
}) {
  return (
    <button type="button" onClick={onClick} className={`ticket home-gate home-gate-${tone} px-5 py-6 pl-8 text-left`}>
      <p className="font-[family-name:var(--font-mono)] text-[11px] tracking-[0.26em] text-[var(--brass)] uppercase">
        {index} · {kicker}
      </p>
      <h2 className="mt-3 font-[family-name:var(--font-display)] text-[1.7rem] leading-none text-[var(--chalk)]">
        {title}
      </h2>
      <p className="mt-3 max-w-sm text-sm leading-relaxed text-[var(--mute)]">{body}</p>
      <span className="mt-5 inline-flex min-h-11 items-center font-[family-name:var(--font-mono)] text-sm text-[var(--brass)]">
        {action} →
      </span>
    </button>
  );
}
