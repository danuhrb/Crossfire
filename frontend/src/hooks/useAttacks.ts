"use client";

import { useState, useEffect, useCallback } from "react";

export interface Attack {
  ip: string;
  lat: number;
  lng: number;
  city: string | null;
  country: string | null;
  country_code: string | null;
  abuse_score: number;
  last_reported: string | null;
}

interface AttackResponse {
  count: number;
  last_updated: number;
  attacks: Attack[];
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const POLL_MS = 30_000;

export function useAttacks() {
  const [attacks, setAttacks] = useState<Attack[]>([]);
  const [loading, setLoading] = useState(true);
  const [lastUpdated, setLastUpdated] = useState<number>(0);

  const fetchAttacks = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/attacks`);
      if (!res.ok) return;
      const data: AttackResponse = await res.json();
      setAttacks(data.attacks);
      setLastUpdated(data.last_updated);
    } catch (err) {
      console.error("Failed to fetch attacks:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAttacks();
    const interval = setInterval(fetchAttacks, POLL_MS);
    return () => clearInterval(interval);
  }, [fetchAttacks]);

  return { attacks, loading, lastUpdated, refetch: fetchAttacks };
}
