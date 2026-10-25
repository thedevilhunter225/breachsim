/**
 * Risk scores are recalculated after every event, so one busy day can hold many points.
 * Charts show one point per day — the score the day ended on — so axis labels are unique.
 */
export function latestPerDay(points: Array<{ date: string; score: number }>): Array<{ date: string; value: number }> {
  const byDay = new Map<string, { date: string; value: number }>();
  for (const point of [...points].sort((a, b) => a.date.localeCompare(b.date))) {
    const day = point.date.slice(0, 10);
    byDay.set(day, { date: day, value: point.score });
  }
  return [...byDay.values()];
}
