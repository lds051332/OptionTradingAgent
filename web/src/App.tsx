import { useEffect, useState } from "react";
import { fetchMe } from "./api";
import { BrandSeal } from "./Brand";
import { Desk } from "./Desk";
import { Home } from "./Home";
import { PageFrame } from "./PageFrame";
import { readStoredLang } from "./i18n";
import { useI18n } from "./locale";
import { useRouter } from "./router";
import type { Defaults } from "./types";

export function App() {
  const { path, navigate } = useRouter();
  const { lang, setLang, t } = useI18n();
  const [ready, setReady] = useState(false);
  const [defaults, setDefaults] = useState<Defaults | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    setError(null);
    try {
      const me = await fetchMe();
      const suggested = me.suggested_language;
      if (!readStoredLang() && (suggested === "zh" || suggested === "en")) {
        setLang(suggested, { persist: false });
      }
      setDefaults(me);
    } catch (err) {
      setDefaults(null);
      setError(err instanceof Error ? err.message : t("common.loadFailed"));
    } finally {
      setReady(true);
    }
  }

  useEffect(() => {
    void refresh();
  }, []);

  useEffect(() => {
    const titles = {
      "/": t("app.titleHome"),
      "/put": t("app.titlePut"),
      "/call": t("app.titleCall"),
    } as const;
    document.title = titles[path as keyof typeof titles] ?? titles["/"];
  }, [path, t]);

  useEffect(() => {
    if (path !== "/" && path !== "/put" && path !== "/call") {
      navigate("/", { replace: true });
    }
  }, [path, navigate]);

  if (!ready) {
    return (
      <div className="flex min-h-dvh flex-col items-center justify-center gap-4 px-6">
        <BrandSeal variant="icon" size="md" alt={t("common.brand")} />
        <p className="font-[family-name:var(--font-mono)] text-sm text-[var(--mute)]">{t("common.loading")}</p>
      </div>
    );
  }

  if (!defaults) {
    return (
      <div className="flex min-h-dvh flex-col items-center justify-center gap-4 px-6 text-center">
        <BrandSeal variant="icon" size="md" alt={t("common.brand")} />
        <p className="max-w-sm text-sm leading-relaxed text-[var(--skip)]">{error ?? t("common.loadFailed")}</p>
        <button
          type="button"
          onClick={() => {
            setReady(false);
            void refresh();
          }}
          className="min-h-11 rounded-sm bg-[var(--brass)] px-5 font-semibold text-[var(--night)]"
        >
          {t("common.retry")}
        </button>
      </div>
    );
  }

  const page =
    path === "/put" || path === "/call" ? (
      <Desk key={`${path}-${lang}`} defaults={defaults} mode={path.slice(1) as "put" | "call"} />
    ) : (
      <Home />
    );

  return <PageFrame>{page}</PageFrame>;
}
