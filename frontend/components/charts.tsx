"use client";

import { useId } from "react";
import { Area, AreaChart, Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

type ChartTheme = "light" | "dark";

function chartColors(theme: ChartTheme) {
  return theme === "dark"
    ? {
        axis: "rgba(236, 244, 255, 0.55)",
        grid: "rgba(236, 244, 255, 0.09)",
        area: "#70e8ff",
        bar: "#6de2f6",
        tooltipBg: "rgba(9, 17, 31, 0.94)",
        tooltipBorder: "rgba(255,255,255,0.08)",
        tooltipText: "#f5fbff",
      }
    : {
        axis: "#5f6777",
        grid: "rgba(19,23,34,0.08)",
        area: "#0f6877",
        bar: "#da5a2a",
        tooltipBg: "rgba(255,255,255,0.98)",
        tooltipBorder: "rgba(19,23,34,0.08)",
        tooltipText: "#131722",
      };
}

export function TrendChart({
  data,
  theme = "light",
}: {
  data: Array<{ date: string; value: number }>;
  theme?: ChartTheme;
}) {
  const id = useId().replace(/:/g, "");
  const gradientId = `${id}-risk`;
  const colors = chartColors(theme);

  return (
    <div className="h-72">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data}>
          <defs>
            <linearGradient id={gradientId} x1="0" x2="0" y1="0" y2="1">
              <stop offset="5%" stopColor={colors.area} stopOpacity={0.42} />
              <stop offset="95%" stopColor={colors.area} stopOpacity={0.03} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="4 4" stroke={colors.grid} />
          <XAxis dataKey="date" tickFormatter={(value) => value.slice(5, 10)} stroke={colors.axis} />
          <YAxis stroke={colors.axis} />
          <Tooltip
            contentStyle={{
              backgroundColor: colors.tooltipBg,
              borderColor: colors.tooltipBorder,
              borderRadius: "1rem",
              color: colors.tooltipText,
              boxShadow: "0 20px 50px rgba(0,0,0,0.18)",
            }}
            labelStyle={{ color: colors.tooltipText }}
            itemStyle={{ color: colors.tooltipText }}
          />
          <Area type="monotone" dataKey="value" stroke={colors.area} fill={`url(#${gradientId})`} strokeWidth={3} />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

export function RiskBandChart({
  data,
  theme = "light",
}: {
  data: Array<{ band: string; count: number }>;
  theme?: ChartTheme;
}) {
  const colors = chartColors(theme);

  return (
    <div className="h-72">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data}>
          <CartesianGrid strokeDasharray="4 4" stroke={colors.grid} />
          <XAxis dataKey="band" stroke={colors.axis} />
          <YAxis stroke={colors.axis} />
          <Tooltip
            contentStyle={{
              backgroundColor: colors.tooltipBg,
              borderColor: colors.tooltipBorder,
              borderRadius: "1rem",
              color: colors.tooltipText,
              boxShadow: "0 20px 50px rgba(0,0,0,0.18)",
            }}
            labelStyle={{ color: colors.tooltipText }}
            itemStyle={{ color: colors.tooltipText }}
          />
          <Bar dataKey="count" fill={colors.bar} radius={[12, 12, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
