import type { ReactNode } from "react";
import { AdSlot } from "./Ads";
import { BrandLockup } from "./Brand";
import { INFO_PAGES, type InfoPageId } from "./infoContent";
import { LangSwitch, useI18n } from "./locale";
import { Link } from "./router";

const LINK_RE = /\[([^\]]+)\]\(([^)\s]+)\)/g;

function richText(text: string): ReactNode[] {
  const out: ReactNode[] = [];
  let last = 0;
  for (const match of text.matchAll(LINK_RE)) {
    const [whole, label, href] = match;
    const at = match.index ?? 0;
    if (at > last) out.push(text.slice(last, at));
    out.push(
      href.startsWith("/") ? (
        <Link key={at} to={href} className="info-link">
          {label}
        </Link>
      ) : (
        <a
          key={at}
          href={href}
          className="info-link"
          {...(href.startsWith("http") ? { target: "_blank", rel: "noopener noreferrer" } : {})}
        >
          {label}
        </a>
      ),
    );
    last = at + whole.length;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}

export function InfoPage({ page }: { page: InfoPageId }) {
  const { lang, t } = useI18n();
  const doc = INFO_PAGES[page][lang];
  return (
    <div className="mx-auto flex min-h-dvh max-w-2xl flex-col px-4 pb-[max(1.5rem,env(safe-area-inset-bottom))] pt-[max(1rem,env(safe-area-inset-top))]">
      <header className="mb-8 flex flex-wrap items-center justify-between gap-3">
        <BrandLockup title={doc.title} />
        <div className="flex shrink-0 items-center gap-2">
          <LangSwitch />
          <Link to="/" className="inline-flex min-h-11 items-center px-2 text-sm text-[var(--mute)]">
            {t("common.back")}
          </Link>
        </div>
      </header>
      <article className="info-doc">
        {doc.updated ? <p className="info-updated">{doc.updated}</p> : null}
        <p className="info-lead">{richText(doc.lead)}</p>
        {doc.sections.map((section) => (
          <section key={section.heading} className="info-section">
            <h2>{section.heading}</h2>
            {section.body.map((paragraph) => (
              <p key={paragraph}>{richText(paragraph)}</p>
            ))}
          </section>
        ))}
      </article>
      {page === "about" ? <AdSlot className="mt-10" /> : null}
    </div>
  );
}
