import { useEffect, useId, useRef, useState, type ReactNode } from "react";

type Rail = "wechat" | "alipay" | "add";
type QrItem = { id: Rail; label: string; src: string; alt: string; app: string };

const qrAssets = import.meta.glob("../../qrcode/*.{png,jpg,jpeg,webp}", {
  eager: true,
  import: "default",
}) as Record<string, string>;

function qrSrc(filename: string): string | undefined {
  const needle = filename.toLowerCase();
  for (const [key, url] of Object.entries(qrAssets)) {
    const base = key.replaceAll("\\", "/").split("/").pop()?.toLowerCase();
    if (base === needle) return url;
  }
  return undefined;
}

function qrItem(
  id: Rail,
  filename: string,
  label: string,
  alt: string,
  app: string,
): QrItem | undefined {
  const src = qrSrc(filename);
  return src ? { id, label, src, alt, app } : undefined;
}

const PAY_RAILS = [
  qrItem("wechat", "wechat.png", "微信", "微信收款码", "微信"),
  qrItem("alipay", "alipay.jpg", "支付宝", "支付宝收款码", "支付宝"),
].filter((item): item is QrItem => item != null);

const CONTACT_RAIL = qrItem("add", "add_wechat.png", "加微信", "个人微信二维码", "微信");
const ALL_RAILS = CONTACT_RAIL ? [...PAY_RAILS, CONTACT_RAIL] : PAY_RAILS;
const HAS_PAY = PAY_RAILS.length > 0;
const HAS_CONTACT = CONTACT_RAIL != null;

type OpenFn = (rail: Rail) => void;

export function PageFrame({ children }: { children: ReactNode }) {
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
        <aside className="page-rail page-rail-pay" aria-label="打赏">
          <PayTicket compact onOpen={setRail} />
        </aside>
      ) : null}
      <div className="page-main">{children}</div>
      {HAS_CONTACT ? (
        <aside className="page-rail page-rail-contact" aria-label="加微信">
          <ContactTicket compact onOpen={setRail} />
        </aside>
      ) : null}
      {HAS_PAY || HAS_CONTACT ? (
        <div className="page-dock">
          {HAS_PAY ? <PayTicket onOpen={setRail} /> : null}
          {HAS_CONTACT ? <ContactTicket onOpen={setRail} /> : null}
        </div>
      ) : null}
      {ALL_RAILS.length > 0 ? (
        <QrDialog rail={rail} onRail={setRail} onClose={() => setRail(null)} />
      ) : null}
    </div>
  );
}

function PayTicket({ compact = false, onOpen }: { compact?: boolean; onOpen: OpenFn }) {
  return (
    <section className={`ticket tip-slip qr-ticket${compact ? " qr-ticket-compact" : ""}`}>
      <p className="qr-kicker">Desk float</p>
      <h2>打赏</h2>
      <p className="qr-body">即将失业的贫穷码农，服务器费用和 token 都是我自掏，随意打赏，万分感谢。</p>
      <QrStack rails={PAY_RAILS} tabs={!compact} onOpen={onOpen} />
      <p className="qr-foot">
        {compact ? "点开放大，长按保存。" : "另一部手机可以直接扫。这部手机请点开放大，长按保存后再用微信或支付宝从相册识别。"}
      </p>
    </section>
  );
}

function ContactTicket({ compact = false, onOpen }: { compact?: boolean; onOpen: OpenFn }) {
  if (!CONTACT_RAIL) return null;
  return (
    <section className={`ticket qr-ticket qr-ticket-contact${compact ? " qr-ticket-compact" : ""}`}>
      <p className="qr-kicker">Contact</p>
      <h2>加微信</h2>
      <p className="qr-body">报 bug、想加功能、或者想聊聊投资，都欢迎加我微信。</p>
      <QrStack rails={[CONTACT_RAIL]} tabs={false} onOpen={onOpen} />
      <p className="qr-foot">{compact ? "点开放大，长按保存。" : "另一部手机可以直接扫。这部手机请点开放大，长按保存后用微信从相册识别。"}</p>
    </section>
  );
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
  const [preview, setPreview] = useState<Rail>(rails[0]?.id ?? "wechat");
  if (rails.length === 0) return null;
  return (
    <div className="qr-stack">
      {tabs && rails.length > 1 ? (
        <div className="tip-tabs tip-preview-tabs" role="tablist" aria-label="收款方式">
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
            <span className="tip-rail-open">点开放大</span>
          </button>
        ))}
      </div>
    </div>
  );
}

function QrDialog({
  rail,
  onRail,
  onClose,
}: {
  rail: Rail | null;
  onRail: (rail: Rail) => void;
  onClose: () => void;
}) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  const current = ALL_RAILS.find((item) => item.id === rail) ?? ALL_RAILS[0];
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
              {pay ? "打赏" : "加微信"}
            </h2>
          </div>
          <button type="button" className="tip-dialog-close" onClick={onClose}>
            关闭
          </button>
        </div>
        {ALL_RAILS.length > 1 ? (
          <div
            className={`tip-tabs tip-dialog-tabs${ALL_RAILS.length === 3 ? " tip-tabs-trio" : ""}`}
            role="tablist"
            aria-label="二维码"
          >
            {ALL_RAILS.map((item) => (
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
          长按保存到相册，打开{current.app}从相册扫一扫。
        </p>
      </div>
    </dialog>
  );
}
