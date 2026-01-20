import logging
import os
from dataclasses import dataclass, asdict
from typing import Optional

import aiohttp

logger = logging.getLogger(__name__)


@dataclass
class GeoResult:
    ip: str
    latitude: float
    longitude: float
    city: Optional[str] = None
    country: Optional[str] = None
    country_code: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


class GeoResolver:
    def __init__(self, db_path: str = None):
        from config import GEOIP_DB_PATH
        self.db_path = db_path or GEOIP_DB_PATH
        self._reader = None
        self._use_maxmind = os.path.exists(self.db_path)

        if self._use_maxmind:
            import geoip2.database
            self._reader = geoip2.database.Reader(self.db_path)
            logger.info(f"Using MaxMind GeoLite2 at {self.db_path}")
        else:
            logger.info("MaxMind DB not found, using ip-api.com fallback")

    def _resolve_maxmind(self, ip: str) -> Optional[GeoResult]:
        import geoip2.errors
        try:
            resp = self._reader.city(ip)
            loc = resp.location
            if loc.latitude is None or loc.longitude is None:
                return None
            return GeoResult(
                ip=ip,
                latitude=loc.latitude,
                longitude=loc.longitude,
                city=resp.city.name,
                country=resp.country.name,
                country_code=resp.country.iso_code,
            )
        except (geoip2.errors.AddressNotFoundError, ValueError):
            return None

    def resolve(self, ip: str) -> Optional[GeoResult]:
        if self._use_maxmind:
            return self._resolve_maxmind(ip)
        return None

    async def resolve_batch_async(self, ips: list[str]) -> list[GeoResult]:
        if self._use_maxmind:
            results = []
            for ip in ips:
                geo = self._resolve_maxmind(ip)
                if geo:
                    results.append(geo)
            return results

        return await self._batch_ip_api(ips)

    """
    WHAT IT DOES
    Resolves a list of IPs to lat/lng via ip-api.com's batch endpoint.

    HOW IT DOES IT
    Chunks the IP list into groups of 100 (api limit per request), POSTs each
    chunk to ip-api.com/batch, and collects successful responses into GeoResults.

    WHY I DID IT THIS WAY
    ip-api.com is free with no key required — serves as a zero-config fallback
    when the MaxMind .mmdb file isn't downloaded yet.
    """
    async def _batch_ip_api(self, ips: list[str]) -> list[GeoResult]:
        results = []
        chunks = [ips[i:i+100] for i in range(0, len(ips), 100)]

        async with aiohttp.ClientSession() as session:
            for chunk in chunks:
                payload = [
                    {"query": ip, "fields": "query,lat,lon,city,country,countryCode,status"}
                    for ip in chunk
                ]
                try:
                    async with session.post(
                        "http://ip-api.com/batch?fields=query,lat,lon,city,country,countryCode,status",
                        json=payload,
                    ) as resp:
                        if resp.status != 200:
                            logger.error(f"ip-api batch returned {resp.status}")
                            continue
                        data = await resp.json()
                        for entry in data:
                            if entry.get("status") != "success":
                                continue
                            results.append(GeoResult(
                                ip=entry["query"],
                                latitude=entry["lat"],
                                longitude=entry["lon"],
                                city=entry.get("city"),
                                country=entry.get("country"),
                                country_code=entry.get("countryCode"),
                            ))
                except Exception as e:
                    logger.error(f"ip-api batch request failed: {e}")

        logger.info(f"Resolved {len(results)}/{len(ips)} IPs to coordinates")
        return results

    def close(self):
        if self._reader:
            self._reader.close()
            self._reader = None
