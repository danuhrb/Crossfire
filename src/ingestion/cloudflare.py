import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import aiohttp

from config import CF_API_TOKEN, CF_ZONE_ID

logger = logging.getLogger(__name__)

CF_API_BASE = "https://api.cloudflare.com/client/v4"


class CloudflareFetcher:
    def __init__(self, token: str = None, zone_id: str = None):
        self.token = token or CF_API_TOKEN
        self.zone_id = zone_id or CF_ZONE_ID
        self._session: Optional[aiohttp.ClientSession] = None

    @property
    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(headers=self._headers)
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    async def _graphql_query(self, query: str, variables: dict = None) -> dict:
        session = await self._get_session()
        payload = {"query": query}
        if variables:
            payload["variables"] = variables

        async with session.post(
            f"{CF_API_BASE}/graphql", json=payload
        ) as resp:
            if resp.status != 200:
                body = await resp.text()
                logger.error(f"CF GraphQL error {resp.status}: {body}")
                raise RuntimeError(f"Cloudflare API returned {resp.status}")
            data = await resp.json()
            if data.get("errors"):
                logger.error(f"CF GraphQL errors: {data['errors']}")
                raise RuntimeError(f"Cloudflare GraphQL errors: {data['errors']}")
            return data["data"]

    async def fetch_traffic_timeseries(self, minutes_back: int = 30) -> list[dict]:
        since = datetime.now(timezone.utc) - timedelta(minutes=minutes_back)
        since_str = since.strftime("%Y-%m-%dT%H:%M:%SZ")

        query = """
        query TrafficTimeSeries($zone: String!, $since: String!) {
            viewer {
                zones(filter: {zoneTag: $zone}) {
                    httpRequests1mGroups(
                        limit: 1000,
                        filter: {datetime_gt: $since}
                        orderBy: [datetime_ASC]
                    ) {
                        dimensions { datetime }
                        sum { requests }
                        uniq { uniques }
                    }
                }
            }
        }
        """
        variables = {"zone": self.zone_id, "since": since_str}
        result = await self._graphql_query(query, variables)

        zones = result.get("viewer", {}).get("zones", [])
        if not zones:
            return []

        groups = zones[0].get("httpRequests1mGroups", [])
        return [
            {
                "timestamp": g["dimensions"]["datetime"],
                "requests": g["sum"]["requests"],
                "unique_visitors": g["uniq"]["uniques"],
            }
            for g in groups
        ]

    async def fetch_firewall_events(
        self, minutes_back: int = 15, limit: int = 500
    ) -> list[dict]:
        since = datetime.now(timezone.utc) - timedelta(minutes=minutes_back)
        since_str = since.strftime("%Y-%m-%dT%H:%M:%SZ")

        query = """
        query FirewallEvents($zone: String!, $since: String!, $limit: Int!) {
            viewer {
                zones(filter: {zoneTag: $zone}) {
                    firewallEventsAdaptive(
                        limit: $limit,
                        filter: {datetime_gt: $since}
                        orderBy: [datetime_DESC]
                    ) {
                        action
                        clientIP
                        clientCountryName
                        clientRequestHTTPMethodName
                        clientRequestPath
                        datetime
                        source
                        userAgent
                        ruleId
                    }
                }
            }
        }
        """
        variables = {
            "zone": self.zone_id,
            "since": since_str,
            "limit": limit,
        }
        result = await self._graphql_query(query, variables)

        zones = result.get("viewer", {}).get("zones", [])
        if not zones:
            return []

        events = zones[0].get("firewallEventsAdaptive", [])
        logger.info(f"Fetched {len(events)} firewall events from last {minutes_back}m")
        return events

    """
    WHAT IT DOES
    Aggregates firewall events by IP, ranks them by hit count, and returns the top N.

    HOW IT DOES IT
    Single pass over events to build per-IP counters (hits, actions, timestamps),
    then sorts descending by hit_count and slices to top_n.

    WHY I DID IT THIS WAY
    Avoids repeated iteration or groupby overhead — one dict accumulation pass
    is O(n) and keeps memory flat since we only store unique IPs.
    """
    async def get_top_attacking_ips(
        self, minutes_back: int = 60, top_n: int = 50
    ) -> list[dict]:
        events = await self.fetch_firewall_events(minutes_back=minutes_back, limit=2000)

        ip_counts: dict[str, dict] = {}
        for ev in events:
            ip = ev.get("clientIP")
            if not ip:
                continue
            if ip not in ip_counts:
                ip_counts[ip] = {
                    "ip": ip,
                    "country": ev.get("clientCountryName", "Unknown"),
                    "hit_count": 0,
                    "actions": set(),
                    "first_seen": ev["datetime"],
                    "last_seen": ev["datetime"],
                }
            ip_counts[ip]["hit_count"] += 1
            ip_counts[ip]["actions"].add(ev.get("action", "unknown"))
            ip_counts[ip]["last_seen"] = max(
                ip_counts[ip]["last_seen"], ev["datetime"]
            )

        ranked = sorted(
            ip_counts.values(), key=lambda x: x["hit_count"], reverse=True
        )[:top_n]

        for entry in ranked:
            entry["actions"] = list(entry["actions"])

        return ranked

    """
    WHAT IT DOES
    Compares the last 5 minutes of traffic against the rolling average to flag spikes.

    HOW IT DOES IT
    Pulls per-minute request counts, splits into historical window vs recent tail,
    and checks if the recent average exceeds the historical by threshold_multiplier.

    WHY I DID IT THIS WAY
    Simple ratio-based detection is cheap to compute on every poll cycle and
    avoids maintaining persistent state between runs.
    """
    async def detect_attack_spike(
        self, threshold_multiplier: float = 3.0, window_minutes: int = 30
    ) -> dict:
        ts = await self.fetch_traffic_timeseries(minutes_back=window_minutes)
        if len(ts) < 5:
            return {"is_spike": False, "reason": "insufficient data"}

        request_counts = [p["requests"] for p in ts]
        avg = sum(request_counts[:-5]) / max(len(request_counts[:-5]), 1)
        recent_avg = sum(request_counts[-5:]) / 5

        is_spike = avg > 0 and (recent_avg / avg) > threshold_multiplier
        return {
            "is_spike": is_spike,
            "rolling_avg": round(avg, 2),
            "recent_avg": round(recent_avg, 2),
            "ratio": round(recent_avg / avg, 2) if avg > 0 else 0,
            "window_minutes": window_minutes,
            "datapoints": len(ts),
        }


async def poll_cloudflare(interval_sec: int = 300):
    fetcher = CloudflareFetcher()
    try:
        while True:
            try:
                spike = await fetcher.detect_attack_spike()
                if spike["is_spike"]:
                    logger.warning(f"Attack spike detected: {spike}")
                    top_ips = await fetcher.get_top_attacking_ips()
                    logger.info(f"Top attackers: {len(top_ips)} IPs")
                    yield {"type": "spike", "spike": spike, "top_ips": top_ips}
                else:
                    top_ips = await fetcher.get_top_attacking_ips(minutes_back=15, top_n=20)
                    if top_ips:
                        yield {"type": "baseline", "top_ips": top_ips}

            except Exception as e:
                logger.exception(f"Error polling Cloudflare: {e}")

            await asyncio.sleep(interval_sec)
    finally:
        await fetcher.close()
