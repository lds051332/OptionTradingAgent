import { useEffect, useId, useRef } from "react";
import { setConsent, useAds } from "./adsense";
import { useI18n } from "./locale";
import { Link } from "./router";

/** Renders nothing until AdSense is configured with a slot and the visitor has made a consent choice. */
export function AdSlot({ className = "" }: { className?: string }) {
  const { t } = useI18n();
  const { config, consent } = useAds();
  const pushed = useRef(false);
  const slot = config?.slot && consent ? config.slot : null;

  useEffect(() => {
    if (!slot || pushed.current) return;
    pushed.current = true;
    try {
      (window.adsbygoogle = window.adsbygoogle ?? []).push({});
    } catch {
      /* AdSense throws if this <ins> was already filled */
    }
  }, [slot]);

  if (!config || !slot) return null;
  return (
    <aside className={`ad-slot ${className}`.trim()} aria-label={t("ads.label")}>
      <p className="ad-slot-label">{t("ads.label")}</p>
      <ins
        className="adsbygoogle"
        style={{ display: "block" }}
        data-ad-client={config.client}
        data-ad-slot={slot}
        data-ad-format="auto"
        data-full-width-responsive="true"
      />
    </aside>
  );
}

export function ConsentBanner() {
  const { t } = useI18n();
  const { config, consent, settingsOpen } = useAds();
  const titleId = useId();
  if (!config || (consent && !settingsOpen)) return null;
  return (
    <div className="consent-bar" role="dialog" aria-labelledby={titleId}>
      <div className="consent-sheet ticket">
        <p id={titleId} className="consent-kicker">
          {t("consent.title")}
        </p>
        <p className="consent-body">
          {t("consent.body")}{" "}
          <Link to="/privacy" className="info-link">
            {t("consent.policy")}
          </Link>
        </p>
        {consent ? (
          <p className="consent-current">
            {t(consent === "granted" ? "consent.currentGranted" : "consent.currentDenied")}
          </p>
        ) : null}
        <div className="consent-actions">
          <button type="button" className="consent-btn" onClick={() => setConsent("denied")}>
            {t("consent.deny")}
          </button>
          <button type="button" className="consent-btn" onClick={() => setConsent("granted")}>
            {t("consent.accept")}
          </button>
        </div>
      </div>
    </div>
  );
}
