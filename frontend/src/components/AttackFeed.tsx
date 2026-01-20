"use client";

import { Attack } from "@/hooks/useAttacks";

const FLAG_URL = "https://flagcdn.com/16x12";

function ThreatBadge({ score }: { score: number }) {
  const bg =
    score >= 95
      ? "bg-red-500/20 text-red-400"
      : score >= 80
        ? "bg-orange-500/20 text-orange-400"
        : "bg-yellow-500/20 text-yellow-400";
  return (
    <span className={`inline-flex px-1.5 py-0.5 rounded text-[10px] font-semibold tabular-nums ${bg}`}>
      {score}%
    </span>
  );
}

function timeAgo(isoStr: string | null): string {
  if (!isoStr) return "—";
  const diff = Date.now() - new Date(isoStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

interface AttackFeedProps {
  attacks: Attack[];
}

export default function AttackFeed({ attacks }: AttackFeedProps) {
  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-4 py-3 border-b border-zinc-800">
        <h2 className="text-sm font-semibold tracking-wide text-zinc-300 uppercase">
          Live Threats
        </h2>
        <div className="flex items-center gap-1.5">
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75" />
            <span className="relative inline-flex rounded-full h-2 w-2 bg-red-500" />
          </span>
          <span className="text-xs text-zinc-500 tabular-nums">{attacks.length}</span>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto">
        {attacks.map((atk, i) => (
          <div
            key={atk.ip}
            className="flex items-center gap-3 px-4 py-2.5 border-b border-zinc-800/50 hover:bg-zinc-800/30 transition-colors animate-fade-in-up"
            style={{ animationDelay: `${Math.min(i * 20, 500)}ms` }}
          >
            {atk.country_code && (
              <img
                src={`${FLAG_URL}/${atk.country_code.toLowerCase()}.png`}
                alt={atk.country_code}
                className="w-4 h-3 rounded-[1px] object-cover opacity-80"
              />
            )}
            <div className="flex-1 min-w-0">
              <p className="text-xs font-mono text-zinc-300 truncate">{atk.ip}</p>
              <p className="text-[11px] text-zinc-500 truncate">
                {[atk.city, atk.country].filter(Boolean).join(", ") || "Unknown"}
              </p>
            </div>
            <div className="flex flex-col items-end gap-0.5 shrink-0">
              <ThreatBadge score={atk.abuse_score} />
              <span className="text-[10px] text-zinc-600">{timeAgo(atk.last_reported)}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
