"use client";

import { Attack } from "@/hooks/useAttacks";

interface StatsBarProps {
  attacks: Attack[];
  lastUpdated: number;
}

export default function StatsBar({ attacks, lastUpdated }: StatsBarProps) {
  const countries = new Set(attacks.map((a) => a.country_code).filter(Boolean));
  const avgScore =
    attacks.length > 0
      ? Math.round(attacks.reduce((s, a) => s + a.abuse_score, 0) / attacks.length)
      : 0;

  const topCountries = Object.entries(
    attacks.reduce<Record<string, number>>((acc, a) => {
      const cc = a.country_code || "??";
      acc[cc] = (acc[cc] || 0) + 1;
      return acc;
    }, {})
  )
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5);

  const updatedStr = lastUpdated
    ? new Date(lastUpdated * 1000).toLocaleTimeString()
    : "—";

  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
      <StatCard label="Active Threats" value={attacks.length.toString()} accent />
      <StatCard label="Countries" value={countries.size.toString()} />
      <StatCard label="Avg Confidence" value={`${avgScore}%`} />
      <StatCard
        label="Top Sources"
        value={topCountries.map(([cc, n]) => `${cc}(${n})`).join("  ")}
        small
      />
    </div>
  );
}

function StatCard({
  label,
  value,
  accent,
  small,
}: {
  label: string;
  value: string;
  accent?: boolean;
  small?: boolean;
}) {
  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-900/50 px-4 py-3">
      <p className="text-[11px] text-zinc-500 uppercase tracking-wider mb-1">{label}</p>
      <p
        className={`font-mono font-semibold tabular-nums ${
          small ? "text-xs text-zinc-400" : "text-lg"
        } ${accent ? "text-red-400" : "text-zinc-200"}`}
      >
        {value}
      </p>
    </div>
  );
}
