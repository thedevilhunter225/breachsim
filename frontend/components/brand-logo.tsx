import clsx from "clsx";
import { useId } from "react";

/**
 * The BreachSim mark: a navy-to-electric-blue shield split by a breach, with
 * circuit traces running into the intact half.
 */
export function BrandShield({ className }: { className?: string }) {
  const id = useId().replace(/:/g, "");
  const plate = `${id}-plate`;
  const edge = `${id}-edge`;
  const bolt = `${id}-bolt`;

  return (
    <svg viewBox="0 0 64 64" className={clsx("h-8 w-8", className)} fill="none" aria-hidden="true">
      <defs>
        <linearGradient id={plate} x1="10" y1="6" x2="46" y2="58" gradientUnits="userSpaceOnUse">
          <stop stopColor="#12305E" />
          <stop offset="0.55" stopColor="#1B4FA0" />
          <stop offset="1" stopColor="#2B8BFF" />
        </linearGradient>
        <linearGradient id={edge} x1="44" y1="8" x2="44" y2="58" gradientUnits="userSpaceOnUse">
          <stop stopColor="#4FA3FF" />
          <stop offset="1" stopColor="#1E6FE0" />
        </linearGradient>
        <linearGradient id={bolt} x1="28" y1="24" x2="36" y2="52" gradientUnits="userSpaceOnUse">
          <stop stopColor="#7CC0FF" />
          <stop offset="1" stopColor="#2B8BFF" />
        </linearGradient>
      </defs>

      {/* Left plate — the circuit-bearing half, torn along the breach line */}
      <path
        d="M32 4 8 12v20c0 12.3 8.6 23.7 20.4 28l1.9-13.6-5.5-.4 6.4-10.8-6.9-1.1 7.7-9.1V4Z"
        fill={`url(#${plate})`}
      />

      {/* Right plate — the intact edge of the shield */}
      <path
        d="M36 4v16.9l-4.6 9.6 6.6.9-6.9 11.4 5.2.5-1.9 21.1C46.9 59.6 56 47.5 56 34.6V12L36 4Z"
        fill={`url(#${edge})`}
        opacity="0.95"
      />

      {/* Breach bolt down the seam */}
      <path
        d="M33.4 19.5 26.6 30.9l5.6.6-5.1 9.8 5.1.5-1.6 12.6 8.1-16.4-5.4-.5 5.6-9.7-5.5-.7 1.4-7.6Z"
        fill={`url(#${bolt})`}
      />

      {/* Circuit traces */}
      <g stroke="#9FD4FF" strokeWidth="1.5" strokeLinecap="round" opacity="0.85">
        <path d="M13 24h6l3-3" />
        <path d="M13 31h9" />
        <path d="M13 38h6l3 3" />
      </g>
      <g fill="#D9EEFF">
        <circle cx="12" cy="24" r="1.9" />
        <circle cx="12" cy="31" r="1.9" />
        <circle cx="12" cy="38" r="1.9" />
      </g>
    </svg>
  );
}

export function BrandLogo({
  compact = false,
  inverted = false,
  tagline = "Human Risk Intelligence",
  className,
}: {
  compact?: boolean;
  inverted?: boolean;
  tagline?: string;
  className?: string;
}) {
  return (
    <div className={clsx("flex items-center gap-2.5", className)}>
      <div
        className={clsx(
          "relative grid h-10 w-10 shrink-0 place-items-center rounded-xl",
          inverted
            ? "bg-white/[0.07] ring-1 ring-inset ring-white/12"
            : "bg-brand-500/8 ring-1 ring-inset ring-brand-500/18",
        )}
      >
        <BrandShield className="h-[1.6rem] w-[1.6rem]" />
      </div>

      {!compact ? (
        <div className="min-w-0">
          <div
            className={clsx(
              "display-font text-[1.15rem] font-bold leading-none",
              inverted ? "text-white" : "text-ink",
            )}
          >
            Breach<span className="text-brand-400">Sim</span>
          </div>
          {tagline ? (
            <div
              className={clsx(
                "mt-1 truncate text-[0.6rem] font-semibold uppercase tracking-[0.19em]",
                inverted ? "text-white/45" : "text-subtle",
              )}
            >
              {tagline}
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
