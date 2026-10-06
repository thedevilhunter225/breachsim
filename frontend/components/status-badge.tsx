export function StatusBadge({ value }: { value: string }) {
  const normalized = value.toLowerCase().replaceAll(" ", "_");
  const tone = ["approved", "consented", "healthy", "completed", "accepted", "low"].includes(normalized)
    ? "bg-signal/10 text-signal"
    : ["pending", "pending_approval", "scheduled", "queued", "medium", "moderate", "degraded", "unknown"].includes(normalized)
      ? "bg-caution/10 text-caution"
      : ["active", "processing", "running"].includes(normalized)
        ? "bg-tide/10 text-tide"
        : ["failed", "bounced", "critical", "high", "revoked", "suspended"].includes(normalized)
          ? "bg-breach/10 text-breach"
          : "bg-surface-sunken text-muted";
  return <span className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded-md px-2 py-1 text-[11px] font-medium capitalize leading-none ${tone}`}><span className="h-1 w-1 rounded-full bg-current" aria-hidden="true" />{value.replaceAll("_", " ")}</span>;
}
