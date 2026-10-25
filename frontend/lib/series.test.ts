import { describe, expect, it } from "vitest";

import { latestPerDay } from "./series";

describe("latestPerDay", () => {
  it("keeps the last score of each day in date order", () => {
    expect(
      latestPerDay([
        { date: "2026-07-26T10:00:00", score: 40 },
        { date: "2026-07-25T09:00:00", score: 10 },
        { date: "2026-07-26T18:30:00", score: 65 },
        { date: "2026-07-26T12:00:00", score: 55 },
      ]),
    ).toEqual([
      { date: "2026-07-25", value: 10 },
      { date: "2026-07-26", value: 65 },
    ]);
  });

  it("returns an empty series for no history", () => {
    expect(latestPerDay([])).toEqual([]);
  });
});
