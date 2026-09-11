import { useEffect, useId, useRef, useState, type MouseEvent, type ReactNode } from "react";
import { useI18n } from "./locale";
import { media } from "./staticMedia";

type Rail = "wechat" | "alipay" | "add";
type QrItem = { id: Rail; label: string; src: string; alt: string; app: string };

const PAYPAL_ME = "https://paypal.me/xxxdashan";
const PAYPAL_AMOUNTS = ["0.99", "4.99", "9.99", "19.99"] as const;

function paypalHref(amount?: string): string {
  return amount ? `${PAYPAL_ME}/${amount}USD` : PAYPAL_ME;
}

function qrItem(
  id: Rail,
  src: string | undefined,
  label: string,
  alt: string,
  app: string,
): QrItem | undefined {
  return src ? { id, label, src, alt, app } : undefined;
}

const HAS_PAYPAL = true;
const HAS_PAY = Boolean(media.qrWechat || media.qrAlipay || HAS_PAYPAL);
const HAS_CONTACT = Boolean(media.qrAddWechat);
const CONTACT_EMAIL = "605465435@qq.com";

type OpenFn = (rail: Rail) => void;

function useRails(): { pay: QrItem[]; contact?: QrItem; all: QrItem[] } {
  const { t } = useI18n();
  const pay = [
    qrItem("wechat", media.qrWechat, t("frame.wechat"), t("frame.wechatAlt"), t("frame.wechat")),
    qrItem("alipay", media.qrAlipay, t("frame.alipay"), t("frame.alipayAlt"), t("frame.alipay")),
  ].filter((item): item is QrItem => item != null);
  const contact = qrItem(
    "add",
    media.qrAddWechat,
    t("frame.addWechat"),
    t("frame.addWechatAlt"),
    t("frame.wechat"),
  );
  return { pay, contact, all: contact ? [...pay, contact] : pay };
}

export function PageFrame({ children }: { children: ReactNode }) {
  const { t } = useI18n();
  const rails = useRails();
  const [rail, setRail] = useState<Rail | null>(null);
  const frameClass = [
    "page-frame",
    HAS_PAY ? "has-pay" : "",
    HAS_CONTACT ? "has-contact" : "",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <div className={frameClass}>
      {HAS_PAY ? (
        <aside className="page-rail page-rail-pay" aria-label={t("frame.payLabel")}>
          <PayTicket compact onOpen={setRail} rails={rails.pay} />
        </aside>
      ) : null}
      <div className="page-main">{children}</div>
      {HAS_CONTACT && rails.contact ? (
        <aside className="page-rail page-rail-contact" aria-label={t("frame.contactLabel")}>
          <ContactTicket compact onOpen={setRail} rail={rails.contact} />
        </aside>
      ) : null}
      {HAS_PAY || HAS_CONTACT ? (
        <div className="page-dock">
          {HAS_PAY ? <PayTicket onOpen={setRail} rails={rails.pay} /> : null}
          {HAS_CONTACT && rails.contact ? <ContactTicket onOpen={setRail} rail={rails.contact} /> : null}
        </div>
      ) : null}
      {rails.all.length > 0 ? (
        <QrDialog rails={rails.all} rail={rail} onRail={setRail} onClose={() => setRail(null)} />
      ) : null}
    </div>
  );
}

function PayTicket({
  compact = false,
  onOpen,
  rails,
}: {
  compact?: boolean;
  onOpen: OpenFn;
  rails: QrItem[];
}) {
  const { t } = useI18n();
  return (
    <section className={`ticket tip-slip qr-ticket${compact ? " qr-ticket-compact" : ""}`}>
      <p className="qr-kicker">Desk float</p>
      <h2>{t("frame.tipTitle")}</h2>
      <p className="qr-body">{t("frame.tipBody")}</p>
      {rails.length > 0 ? (
        <>
          <QrStack rails={rails} tabs={rails.length > 1} onOpen={onOpen} />
          <p className="qr-foot">{compact ? t("frame.tipFootCompact") : t("frame.tipFoot")}</p>
        </>
      ) : null}
      {HAS_PAYPAL ? <PaypalTip compact={compact} /> : null}
    </section>
  );
}

function ContactTicket({
  compact = false,
  onOpen,
  rail,
}: {
  compact?: boolean;
  onOpen: OpenFn;
  rail: QrItem;
}) {
  const { t } = useI18n();
  return (
    <section className={`ticket qr-ticket qr-ticket-contact${compact ? " qr-ticket-compact" : ""}`}>
      <p className="qr-kicker">Contact</p>
      <h2>{t("frame.contactTitle")}</h2>
      <p className="qr-body">{t("frame.contactBody")}</p>
      <ContactEmail />
      <QrStack rails={[rail]} tabs={false} onOpen={onOpen} />
      <p className="qr-foot">{compact ? t("frame.contactFootCompact") : t("frame.contactFoot")}</p>
    </section>
  );
}

function PaypalTip({ compact = false }: { compact?: boolean }) {
  const { t } = useI18n();
  return (
    <div className="paypal-slip">
      <p className="paypal-kicker">{t("frame.paypal")}</p>
      <p className="paypal-hint">{compact ? t("frame.paypalHintCompact") : t("frame.paypalHint")}</p>
      <div className="paypal-amounts" role="group" aria-label={t("frame.paypalAmounts")}>
        {PAYPAL_AMOUNTS.map((amount) => {
          const label = `$${amount}`;
          return (
            <a
              key={amount}
              className="paypal-amt"
              href={paypalHref(amount)}
              target="_blank"
              rel="noopener noreferrer"
              aria-label={t("frame.paypalAmount", { amount: label })}
            >
              {label}
            </a>
          );
        })}
        <a
          className="paypal-amt paypal-custom"
          href={paypalHref()}
          target="_blank"
          rel="noopener noreferrer"
          aria-label={t("frame.paypalCustomAria")}
        >
          {t("frame.paypalCustom")}
        </a>
      </div>
    </div>
  );
}

function ContactEmail() {
  const { t } = useI18n();
  const [copied, setCopied] = useState(false);
  const copiedTimer = useRef<number>(0);
  const [local, domain] = CONTACT_EMAIL.split("@");

  useEffect(() => {
    return () => window.clearTimeout(copiedTimer.current);
  }, []);

  async function copyEmail(event: MouseEvent<HTMLAnchorElement>) {
    event.preventDefault();
    const ok = await writeClipboard(CONTACT_EMAIL);
    if (ok) {
      setCopied(true);
      window.clearTimeout(copiedTimer.current);
      copiedTimer.current = window.setTimeout(() => setCopied(false), 1800);
      return;
    }
    window.location.href = `mailto:${CONTACT_EMAIL}`;
  }

  return (
    <a
      className={`contact-email${copied ? " is-copied" : ""}`}
      href={`mailto:${CONTACT_EMAIL}`}
      onClick={(event) => void copyEmail(event)}
      aria-label={`${t("frame.contactEmailLabel")} ${CONTACT_EMAIL}`}
    >
      <span className="contact-email-label">{t("frame.contactEmailLabel")}</span>
      <span className="contact-email-addr">
        {local}@<wbr />
        {domain}
      </span>
      <span className="contact-email-hint" aria-live="polite">
        {copied ? t("frame.contactEmailCopied") : t("frame.contactEmailCopy")}
      </span>
    </a>
  );
}

async function writeClipboard(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    const input = document.createElement("input");
    input.value = text;
    input.setAttribute("readonly", "");
    input.style.position = "fixed";
    input.style.opacity = "0";
    document.body.appendChild(input);
    input.select();
    input.setSelectionRange(0, text.length);
    const ok = document.execCommand("copy");
    document.body.removeChild(input);
    return ok;
  }
}

function QrStack({
  rails,
  tabs,
  onOpen,
}: {
  rails: QrItem[];
  tabs: boolean;
  onOpen: OpenFn;
}) {
  const { t } = useI18n();
  const [preview, setPreview] = useState<Rail>(rails[0]?.id ?? "wechat");
  if (rails.length === 0) return null;
  return (
    <div className="qr-stack">
      {tabs && rails.length > 1 ? (
        <div className="tip-tabs tip-preview-tabs" role="tablist" aria-label={t("frame.payMethods")}>
          {rails.map((item) => (
            <button
              key={item.id}
              type="button"
              role="tab"
              aria-selected={preview === item.id}
              className={preview === item.id ? "is-on" : ""}
              onClick={() => setPreview(item.id)}
            >
              {item.label}
            </button>
          ))}
        </div>
      ) : null}
      <div className="tip-rails">
        {rails.map((item) => (
          <button
            key={item.id}
            type="button"
            className={`tip-rail${tabs && preview !== item.id ? " is-parked" : ""}`}
            onClick={() => onOpen(item.id)}
          >
            <span className="tip-rail-label">{item.label}</span>
            <img src={item.src} alt={item.alt} width={432} height={450} draggable={false} />
            <span className="tip-rail-open">{t("frame.openQr")}</span>
          </button>
        ))}
      </div>
    </div>
  );
}

function QrDialog({
  rails,
  rail,
  onRail,
  onClose,
}: {
  rails: QrItem[];
  rail: Rail | null;
  onRail: (rail: Rail) => void;
  onClose: () => void;
}) {
  const { t } = useI18n();
  const dialogRef = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  const current = rails.find((item) => item.id === rail) ?? rails[0];
  const pay = current.id !== "add";

  useEffect(() => {
    const node = dialogRef.current;
    if (!node) return;
    if (rail && !node.open) node.showModal();
    if (!rail && node.open) node.close();
  }, [rail]);

  return (
    <dialog
      ref={dialogRef}
      className="tip-dialog"
      aria-labelledby={titleId}
      onClose={onClose}
      onClick={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div className="tip-dialog-sheet">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="font-[family-name:var(--font-mono)] text-[11px] tracking-[0.26em] text-[var(--brass)] uppercase">
              {pay ? "Desk float" : "Contact"}
            </p>
            <h2 id={titleId} className="mt-1 font-[family-name:var(--font-display)] text-2xl text-[var(--chalk)]">
              {pay ? t("frame.tipTitle") : t("frame.contactTitle")}
            </h2>
          </div>
          <button type="button" className="tip-dialog-close" onClick={onClose}>
            {t("frame.close")}
          </button>
        </div>
        {rails.length > 1 ? (
          <div
            className={`tip-tabs tip-dialog-tabs${rails.length === 3 ? " tip-tabs-trio" : ""}`}
            role="tablist"
            aria-label={t("frame.qrLabel")}
          >
            {rails.map((item) => (
              <button
                key={item.id}
                type="button"
                role="tab"
                aria-selected={current.id === item.id}
                className={current.id === item.id ? "is-on" : ""}
                onClick={() => onRail(item.id)}
              >
                {item.label}
              </button>
            ))}
          </div>
        ) : null}
        <img
          src={current.src}
          alt={current.alt}
          width={432}
          height={450}
          draggable={false}
          className="tip-dialog-qr"
        />
        <p className="mt-3 text-center text-[12px] leading-relaxed text-[var(--mute)]">
          {t("frame.saveScan", { app: current.app })}
        </p>
      </div>
    </dialog>
  );
}
