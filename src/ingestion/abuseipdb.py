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

    CATEGORY_DDOS = 4

    async def report_ip(
        self,
        ip: str,
        categories: list[int] = None,
        comment: str = "",
    ) -> dict:
        session = await self._get_session()
        payload = {
            "ip": ip,
            "categories": ",".join(str(c) for c in (categories or [self.CATEGORY_DDOS])),
            "comment": comment,
        }

        async with session.post(
            f"{ABUSEIPDB_BASE}/report", data=payload
        ) as resp:
            if resp.status == 429:
                logger.warning("AbuseIPDB rate limit hit during report")
                return {"ip": ip, "error": "rate_limited"}
            if resp.status != 200:
                body = await resp.text()
                logger.error(f"AbuseIPDB report error {resp.status}: {body}")
                return {"ip": ip, "error": f"status_{resp.status}"}

            data = await resp.json()
            result = data.get("data", {})
            logger.info(
                f"Reported {ip} — new score: {result.get('abuseConfidenceScore')}"
            )
            return {
                "ip": result.get("ipAddress", ip),
                "abuse_score": result.get("abuseConfidenceScore", 0),
            }

    """
    WHAT IT DOES
    Takes a list of model-flagged IPs with their confidence scores and reports
    each one to AbuseIPDB with the DDoS category and a generated comment.

    HOW IT DOES IT
    Iterates over flagged IPs, skips any below the confidence floor, builds a
    comment string with the model confidence, and calls the report endpoint
    sequentially to stay within rate limits.

    WHY I DID IT THIS WAY
    Sequential reporting avoids hammering the API and getting 429'd. The confidence
    floor prevents low-signal IPs from polluting the AbuseIPDB database with
    false positives from an untrained or poorly calibrated model.
    """
    async def report_flagged_ips(
        self,
        flagged: list[dict],
        confidence_floor: float = 0.90,
    ) -> list[dict]:
        results = []
        for entry in flagged:
            ip = entry.get("ip")
            confidence = entry.get("confidence", 0)
            if not ip or confidence < confidence_floor:
                continue

            comment = (
                f"Crossfire DDoS classifier flagged this IP with "
                f"{confidence:.1%} confidence"
            )
            result = await self.report_ip(ip, comment=comment)
            results.append(result)

        logger.info(
            f"Reported {len(results)}/{len(flagged)} flagged IPs to AbuseIPDB"
        )
        return results
