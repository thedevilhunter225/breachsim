import clsx from "clsx";
import { useId } from "react";

export function BrandLogo({
  compact = false,
  inverted = false,
  className,
}: {
  compact?: boolean;
  inverted?: boolean;
  className?: string;
}) {
  const id = useId().replace(/:/g, "");
  const shieldGradient = `${id}-shield`;
  const coreGradient = `${id}-core`;
  const glowGradient = `${id}-glow`;

  return (
    <div className={clsx("flex items-center gap-3", className)}>
      <div className="relative grid h-12 w-12 place-items-center rounded-[1.35rem] border border-white/12 bg-[linear-gradient(180deg,rgba(11,17,30,0.94),rgba(9,21,42,0.88))] shadow-[0_18px_44px_rgba(3,12,28,0.42)]">
        <div className="absolute inset-[5px] rounded-[1.1rem] bg-[radial-gradient(circle_at_top,rgba(112,236,255,0.2),transparent_55%),linear-gradient(180deg,rgba(17,39,68,0.85),rgba(8,18,35,0.98))]" />
        <svg viewBox="0 0 64 64" className="relative z-10 h-8 w-8" fill="none" aria-hidden="true">
          <defs>
            <linearGradient id={shieldGradient} x1="32" y1="8" x2="32" y2="56" gradientUnits="userSpaceOnUse">
              <stop stopColor="#63E8FF" />
              <stop offset="0.5" stopColor="#2E8BFF" />
              <stop offset="1" stopColor="#0A2344" />
            </linearGradient>
            <linearGradient id={coreGradient} x1="24" y1="20" x2="41" y2="48" gradientUnits="userSpaceOnUse">
              <stop stopColor="#D7FFFF" />
              <stop offset="1" stopColor="#51C9FF" />
            </linearGradient>
            <linearGradient id={glowGradient} x1="19" y1="15" x2="43" y2="47" gradientUnits="userSpaceOnUse">
              <stop stopColor="rgba(255,255,255,0.88)" />
              <stop offset="1" stopColor="rgba(255,255,255,0)" />
            </linearGradient>
          </defs>
          <path
            d="M32 6.5 49.5 13.7V27.7c0 11.2-7.1 21.5-17.5 25.5C21.6 49.2 14.5 39 14.5 27.7V13.7L32 6.5Z"
            fill={`url(#${shieldGradient})`}
            stroke="rgba(215,255,255,0.9)"
            strokeWidth="2.4"
          />
          <path
            d="M32.2 16 23.6 31.1h7l-3.4 14 13.2-18.2h-7.6l4-10.9Z"
            fill={`url(#${coreGradient})`}
            stroke="rgba(255,255,255,0.82)"
            strokeLinejoin="round"
            strokeWidth="1.4"
          />
          <path d="M20.2 16.2c4.3-3.2 8.9-4.9 13.8-5.2" stroke={`url(#${glowGradient})`} strokeLinecap="round" strokeWidth="1.6" />
        </svg>
      </div>

      {!compact ? (
        <div>
          <div className={clsx("display-font text-[1.35rem] font-semibold tracking-[-0.04em]", inverted ? "text-white" : "text-ink")}>
            BreachSim
          </div>
          <div className={clsx("mt-0.5 text-[0.68rem] uppercase tracking-[0.26em]", inverted ? "text-white/52" : "text-slate")}>
            Human Risk Intelligence
          </div>
        </div>
      ) : null}
    </div>
  );
}
