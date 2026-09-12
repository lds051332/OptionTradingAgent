import { createContext, useContext, useMemo, useState, type ReactNode } from "react";
import { detectLang, setActiveLang, t as translate, type Lang, type MsgKey } from "./i18n";

type LocaleCtx = {
  lang: Lang;
  setLang: (lang: Lang, options?: { persist?: boolean }) => void;
  t: (key: MsgKey, vars?: Record<string, string | number>) => string;
};

const LocaleContext = createContext<LocaleCtx | null>(null);

export function LocaleProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(() => {
    const initial = detectLang();
    setActiveLang(initial, { persist: false });
    return initial;
  });

  const value = useMemo<LocaleCtx>(() => {
    return {
      lang,
      setLang: (next, options) => {
        setActiveLang(next, options);
        setLangState(next);
      },
      t: (key, vars) => translate(lang, key, vars),
    };
  }, [lang]);

  return <LocaleContext.Provider value={value}>{children}</LocaleContext.Provider>;
}

export function useI18n(): LocaleCtx {
  const ctx = useContext(LocaleContext);
  if (!ctx) throw new Error("useI18n must be used within LocaleProvider");
  return ctx;
}

export function LangSwitch() {
  const { lang, setLang, t } = useI18n();
  return (
    <div className="lang-switch" role="group" aria-label={t("common.lang")}>
      <button
        type="button"
        className={lang === "en" ? "is-on" : ""}
        aria-pressed={lang === "en"}
        onClick={() => setLang("en")}
      >
        EN
      </button>
      <button
        type="button"
        className={lang === "zh" ? "is-on" : ""}
        aria-pressed={lang === "zh"}
        onClick={() => setLang("zh")}
      >
        中文
      </button>
    </div>
  );
}
