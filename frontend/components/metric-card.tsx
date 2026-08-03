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
    <div className={`app-surface rounded-xl p-4 ${toneMap[tone]}`}>
      <div className="text-[0.65rem] font-semibold uppercase tracking-[0.13em] text-slate">{label}</div>
      <div className="mt-3 display-font text-2xl font-semibold tracking-[-0.04em]">{value}</div>
    </div>
  );
}
