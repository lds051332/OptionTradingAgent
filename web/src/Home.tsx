import { BrandLockup } from "./Brand";
import { LangSwitch, useI18n } from "./locale";
import { Link } from "./router";

export function Home() {
  const { t } = useI18n();
  return (
    <div className="mx-auto flex min-h-dvh max-w-2xl flex-col px-4 pb-[max(1.5rem,env(safe-area-inset-bottom))] pt-[max(1rem,env(safe-area-inset-top))]">
      <header className="mb-8 flex flex-wrap items-center justify-between gap-3">
        <BrandLockup title={t("home.title")} />
        <LangSwitch />
      </header>

      <p className="mb-6 max-w-md text-sm leading-relaxed text-[var(--mute)]">{t("home.lead")}</p>

      <div className="flex flex-col gap-4">
        <GateCard
          index="01"
          kicker="Cash book"
          title={t("home.putTitle")}
          body={t("home.putBody")}
          action={t("home.putAction")}
          tone="cash"
          to="/put"
        />
        <GateCard
          index="02"
          kicker="Stock book"
          title={t("home.callTitle")}
          body={t("home.callBody")}
          action={t("home.callAction")}
          tone="stock"
          to="/call"
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
  to,
}: {
  index: string;
  kicker: string;
  title: string;
  body: string;
  action: string;
  tone: "cash" | "stock";
  to: string;
}) {
  return (
    <Link to={to} className={`ticket home-gate home-gate-${tone} px-5 py-6 pl-8 text-left`}>
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
    </Link>
  );
}
