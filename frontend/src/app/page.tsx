"use client";

import Globe from "@/components/Globe";
import AttackFeed from "@/components/AttackFeed";
import StatsBar from "@/components/StatsBar";
import { useAttacks } from "@/hooks/useAttacks";

export default function Home() {
  const { attacks, loading, lastUpdated } = useAttacks();

  const markers = attacks.map((a) => ({
    lat: a.lat,
    lng: a.lng,
    size: Math.max(0.03, Math.min(a.abuse_score / 800, 0.12)),
  }));

  return (
    <main className="min-h-screen flex flex-col">
      {/* Header */}
      <header className="flex items-center justify-between px-6 py-4 border-b border-zinc-800">
        <div className="flex items-center gap-3">
          <div className="h-8 w-8 rounded-lg bg-red-500/10 flex items-center justify-center">
            <svg className="w-4 h-4 text-red-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          <div>
            <h1 className="text-base font-semibold tracking-tight">Crossfire</h1>
            <p className="text-xs text-zinc-500">Real-time DDoS Attack Map</p>
          </div>
        </div>
        <div className="flex items-center gap-2 text-xs text-zinc-500">
          {lastUpdated > 0 && (
            <span className="font-mono">
              Updated {new Date(lastUpdated * 1000).toLocaleTimeString()}
            </span>
          )}
        </div>
      </header>

      {/* Stats */}
      <div className="px-6 py-4">
        <StatsBar attacks={attacks} lastUpdated={lastUpdated} />
      </div>

      {/* Main Content */}
      <div className="flex-1 flex flex-col lg:flex-row gap-0 lg:gap-0 px-6 pb-6">
        {/* Globe */}
        <div className="flex-1 flex items-center justify-center relative min-h-[400px]">
          {loading && attacks.length === 0 ? (
            <div className="flex flex-col items-center gap-3">
              <div className="h-8 w-8 border-2 border-zinc-700 border-t-red-500 rounded-full animate-spin" />
              <p className="text-sm text-zinc-500">Loading threat data...</p>
            </div>
          ) : (
            <div className="w-full max-w-[600px]">
              <Globe markers={markers} className="w-full" />
            </div>
          )}
        </div>

        {/* Attack Feed */}
        <div className="w-full lg:w-80 xl:w-96 border border-zinc-800 rounded-lg bg-zinc-900/30 max-h-[600px] overflow-hidden flex flex-col">
          <AttackFeed attacks={attacks} />
        </div>
      </div>
    </main>
  );
}
