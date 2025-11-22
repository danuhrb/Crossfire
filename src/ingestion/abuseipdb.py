import logging
from typing import Optional

import aiohttp

from config import ABUSEIPDB_API_KEY

logger = logging.getLogger(__name__)

ABUSEIPDB_BASE = "https://api.abuseipdb.com/api/v2"


class AbuseIPDBClient:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or ABUSEIPDB_API_KEY
        self._session: Optional[aiohttp.ClientSession] = None

    @property
    def _headers(self) -> dict:
        return {
            "Key": self.api_key,
            "Accept": "application/json",
        }

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(headers=self._headers)
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    async def check_ip(self, ip: str, max_age_days: int = 90) -> dict:
        session = await self._get_session()
        params = {"ipAddress": ip, "maxAgeInDays": max_age_days, "verbose": ""}

        async with session.get(
            f"{ABUSEIPDB_BASE}/check", params=params
        ) as resp:
            if resp.status == 429:
                logger.warning("AbuseIPDB rate limit hit")
                return {"ip": ip, "error": "rate_limited"}
            if resp.status != 200:
                body = await resp.text()
                logger.error(f"AbuseIPDB check error {resp.status}: {body}")
                return {"ip": ip, "error": f"status_{resp.status}"}

            data = await resp.json()
            result = data.get("data", {})
            return {
                "ip": result.get("ipAddress", ip),
                "abuse_score": result.get("abuseConfidenceScore", 0),
                "country_code": result.get("countryCode"),
                "isp": result.get("isp"),
                "domain": result.get("domain"),
                "total_reports": result.get("totalReports", 0),
                "num_distinct_users": result.get("numDistinctUsers", 0),
                "last_reported": result.get("lastReportedAt"),
                "is_tor": result.get("isTor", False),
                "usage_type": result.get("usageType"),
            }

    async def get_blacklist(
        self, confidence_minimum: int = 90, limit: int = 500
    ) -> list[dict]:
        session = await self._get_session()
        params = {
            "confidenceMinimum": confidence_minimum,
            "limit": limit,
        }

        async with session.get(
            f"{ABUSEIPDB_BASE}/blacklist", params=params
        ) as resp:
            if resp.status != 200:
                body = await resp.text()
                logger.error(f"AbuseIPDB blacklist error {resp.status}: {body}")
                return []

            data = await resp.json()
            entries = data.get("data", [])
            logger.info(
                f"Fetched {len(entries)} blacklisted IPs "
                f"(confidence >= {confidence_minimum})"
            )
            return [
                {
                    "ip": e.get("ipAddress"),
                    "abuse_score": e.get("abuseConfidenceScore", 0),
                    "country_code": e.get("countryCode"),
                    "last_reported": e.get("lastReportedAt"),
                }
                for e in entries
            ]

    async def enrich_ips(self, ips: list[str]) -> list[dict]:
        results = []
        for ip in ips:
            result = await self.check_ip(ip)
            results.append(result)
        return results
