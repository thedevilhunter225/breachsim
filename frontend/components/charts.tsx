"use client";

import { useId } from "react";
import { Area, AreaChart, Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

type ChartTheme = "light" | "dark";

/** Chart palette drawn from the BreachSim brand ramp so charts match the shell. */
function chartColors(theme: ChartTheme) {
  return theme === "dark"
    ? {
        axis: "rgba(231, 239, 250, 0.5)",
        grid: "rgba(231, 239, 250, 0.08)",
        area: "#85acf0",
        bar: "#85acf0",
        tooltipBg: "rgba(12, 25, 48, 0.96)",
        tooltipBorder: "rgba(255,255,255,0.1)",
        tooltipText: "#e7effa",
      }
    : {
        axis: "#5c6c85",
        grid: "rgba(12,21,40,0.07)",
        area: "#467acb",
        bar: "#467acb",
        tooltipBg: "rgba(255,255,255,0.98)",
        tooltipBorder: "rgba(12,21,40,0.09)",
        tooltipText: "#0c1528",
      };
}

/** Risk bands escalate from safe to critical, so the bars should too. */
const RISK_BAND_COLORS: Record<string, string> = {
  "0-25": "#408f81",
  "26-50": "#6994d1",
  "51-75": "#d4a85a",
  "76-100": "#cf6e73",
};

export function TrendChart({
  data,
  theme = "light",
  compact = false,
}: {
  data: Array<{ date: string; value: number }>;
  theme?: ChartTheme;
  compact?: boolean;
}) {
  const id = useId().replace(/:/g, "");
  const gradientId = `${id}-risk`;
  const colors = chartColors(theme);

  return (
    <div className={compact ? "h-60" : "h-72"}>
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data}>
          <defs>
            <linearGradient id={gradientId} x1="0" x2="0" y1="0" y2="1">
              <stop offset="5%" stopColor={colors.area} stopOpacity={0.16} />
              <stop offset="95%" stopColor={colors.area} stopOpacity={0.03} />
            </linearGradient>
          </defs>
          <CartesianGrid vertical={false} strokeDasharray="3 5" stroke={colors.grid} />
          <XAxis dataKey="date" tickFormatter={(value) => value.slice(5, 10)} stroke={colors.axis} tickLine={false} axisLine={false} fontSize={11} />
          <YAxis stroke={colors.axis} tickLine={false} axisLine={false} fontSize={11} width={32} allowDecimals={false} />
          <Tooltip
            contentStyle={{
              backgroundColor: colors.tooltipBg,
              borderColor: colors.tooltipBorder,
              borderRadius: "0.5rem",
              color: colors.tooltipText,
              boxShadow: "0 4px 18px rgba(0,0,0,0.08)",
            }}
            labelStyle={{ color: colors.tooltipText }}
            itemStyle={{ color: colors.tooltipText }}
          />
          <Area type="monotone" dataKey="value" name="Recorded value" stroke={colors.area} fill={`url(#${gradientId})`} strokeWidth={2} isAnimationActive={false} />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

export function RiskBandChart({
  data,
  theme = "light",
  compact = false,
}: {
  data: Array<{ band: string; count: number }>;
  theme?: ChartTheme;
  compact?: boolean;
}) {
  const colors = chartColors(theme);
  // Recharts reads a per-datum `fill`, which colour-codes the bands without needing
  // <Cell> children (those render an empty rectangle group in this version).
  const banded = data.map((entry) => ({
    ...entry,
    fill: RISK_BAND_COLORS[entry.band] ?? colors.bar,
  }));

  return (
    <div className={compact ? "h-48" : "h-72"}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={banded}>
          <CartesianGrid vertical={false} strokeDasharray="3 5" stroke={colors.grid} />
          <XAxis dataKey="band" stroke={colors.axis} tickLine={false} axisLine={false} fontSize={11} />
          <YAxis stroke={colors.axis} tickLine={false} axisLine={false} fontSize={11} width={28} allowDecimals={false} />
          <Tooltip
            contentStyle={{
              backgroundColor: colors.tooltipBg,
              borderColor: colors.tooltipBorder,
              borderRadius: "0.5rem",
              color: colors.tooltipText,
              boxShadow: "0 4px 18px rgba(0,0,0,0.08)",
            }}
            labelStyle={{ color: colors.tooltipText }}
            itemStyle={{ color: colors.tooltipText }}
          />
          <Bar dataKey="count" name="People" radius={[4, 4, 0, 0]} maxBarSize={44} fill={colors.bar} isAnimationActive={false} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
