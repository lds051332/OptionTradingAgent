import icon from "./assets/morgan-dashan-icon.png";
import mark from "./assets/morgan-dashan-mark.png";

type SealSize = "sm" | "md" | "lg";

const SEAL_PX: Record<SealSize, number> = {
  sm: 40,
  md: 48,
  lg: 144,
};

export function BrandSeal({
  variant = "icon",
  size = "md",
  className = "",
  alt = "",
}: {
  variant?: "icon" | "mark";
  size?: SealSize;
  className?: string;
  alt?: string;
}) {
  const px = SEAL_PX[size];
  return (
    <img
      src={variant === "mark" ? mark : icon}
      alt={alt}
      width={px}
      height={px}
      draggable={false}
      className={`brand-seal ${className}`.trim()}
      style={{ width: px, height: px }}
    />
  );
}

export function BrandLockup({ title }: { title: string }) {
  return (
    <div className="flex min-w-0 items-center gap-3">
      <BrandSeal variant="icon" size="md" />
      <div className="min-w-0">
        <p className="font-[family-name:var(--font-display)] text-[13px] tracking-[0.22em] text-[var(--brass)]">
          摩根大山
        </p>
        <h1 className="font-[family-name:var(--font-display)] text-[1.7rem] leading-none text-[var(--chalk)]">
          {title}
        </h1>
      </div>
    </div>
  );
}
