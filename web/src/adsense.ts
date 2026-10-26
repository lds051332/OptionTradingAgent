import { useSyncExternalStore } from "react";
import type { AdsConfig } from "./types";

export type Consent = "granted" | "denied";

type AdsState = {
  config: AdsConfig | null;
  consent: Consent | null;
  settingsOpen: boolean;
};

declare global {
  interface Window {
    adsbygoogle?: unknown[];
    dataLayer?: unknown[];
  }
}

const CONSENT_KEY = "option-desk:ad-consent";
const SCRIPT_ID = "adsbygoogle-js";

let state: AdsState = { config: null, consent: readConsent(), settingsOpen: false };
const listeners = new Set<() => void>();

function readConsent(): Consent | null {
  try {
    const stored = window.localStorage.getItem(CONSENT_KEY);
    return stored === "granted" || stored === "denied" ? stored : null;
  } catch {
    return null;
  }
}

function update(patch: Partial<AdsState>): void {
  state = { ...state, ...patch };
  listeners.forEach((listener) => listener());
}

/** gtag must be a real `arguments` push; AdSense ignores plain arrays in dataLayer. */
function gtag(..._args: unknown[]): void {
  window.dataLayer = window.dataLayer ?? [];
  window.dataLayer.push(arguments);
}

function consentSignals(consent: Consent) {
  const value = consent === "granted" ? "granted" : "denied";
  return { ad_storage: value, ad_user_data: value, ad_personalization: value, analytics_storage: "denied" };
}

/** Load AdSense only after the visitor has chosen; Consent Mode tells it which ads it may serve. */
function syncScript(): void {
  const { config, consent } = state;
  if (!config || !consent) return;
  if (!document.getElementById(SCRIPT_ID)) {
    gtag("consent", "default", consentSignals("denied"));
    gtag("consent", "update", consentSignals(consent));
    const script = document.createElement("script");
    script.id = SCRIPT_ID;
    script.async = true;
    script.crossOrigin = "anonymous";
    script.src = `https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=${encodeURIComponent(config.client)}`;
    document.head.appendChild(script);
    return;
  }
  gtag("consent", "update", consentSignals(consent));
}

export function configureAds(config: AdsConfig | null | undefined): void {
  update({ config: config ?? null });
  syncScript();
}

export function setConsent(consent: Consent): void {
  try {
    window.localStorage.setItem(CONSENT_KEY, consent);
  } catch {
    /* ignore */
  }
  update({ consent, settingsOpen: false });
  syncScript();
}

export function openConsentSettings(): void {
  update({ settingsOpen: true });
}

export function useAds(): AdsState {
  return useSyncExternalStore(
    (listener) => {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    () => state,
  );
}
