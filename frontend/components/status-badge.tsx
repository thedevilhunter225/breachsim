export function StatusBadge({ value }: { value: string }) {
  const normalized = value.toLowerCase();
  const styles =
    normalized === "approved" || normalized === "consented" || normalized === "operator ready"
      ? "bg-moss/15 text-moss"
      : normalized === "pending" || normalized === "pending_approval"
        ? "bg-warning/15 text-amber-700"
        : normalized === "active"
          ? "bg-tide/15 text-tide"
          : normalized === "high"
            ? "bg-ember/10 text-ember"
            : normalized === "medium"
              ? "bg-warning/15 text-amber-700"
              : normalized === "low"
                ? "bg-moss/15 text-moss"
          : "bg-ember/15 text-ember";

  return <span className={`inline-flex items-center rounded-full px-2.5 py-1 text-[0.68rem] font-bold capitalize leading-none ${styles}`}>{value.replaceAll("_", " ")}</span>;
}
