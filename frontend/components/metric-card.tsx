export function MetricCard({
  label,
  value,
  tone = "ink",
}: {
  label: string;
  value: string | number;
  tone?: "ink" | "ember" | "tide" | "moss";
}) {
  const toneMap = {
    ink: "text-ink bg-white/80",
    ember: "text-ember bg-ember/5",
    tide: "text-tide bg-tide/5",
    moss: "text-moss bg-moss/10",
  };

  return (
    <div className={`shell-ring rounded-[1.65rem] border border-white/65 p-5 shadow-card ${toneMap[tone]}`}>
      <div className="text-[0.68rem] uppercase tracking-[0.24em] text-slate">{label}</div>
      <div className="mt-5 flex items-end justify-between gap-3">
        <div className="display-font text-3xl font-semibold tracking-[-0.04em]">{value}</div>
        <div className="h-10 w-10 rounded-2xl border border-ink/10 bg-white/70" />
      </div>
    </div>
  );
}
