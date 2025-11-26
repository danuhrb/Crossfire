"""
IP to geographic coordinate resolution using MaxMind GeoLite2.
"""

import logging
from dataclasses import dataclass
from typing import Optional

import geoip2.database
import geoip2.errors

from config import GEOIP_DB_PATH

logger = logging.getLogger(__name__)


@dataclass
class GeoResult:
    ip: str
    latitude: float
    longitude: float
    city: Optional[str] = None
    country: Optional[str] = None
    country_code: Optional[str] = None


class GeoResolver:
    def __init__(self, db_path: str = None):
        self.db_path = db_path or GEOIP_DB_PATH
        self._reader = None

    def _get_reader(self) -> geoip2.database.Reader:
        if self._reader is None:
            self._reader = geoip2.database.Reader(self.db_path)
        return self._reader

    def resolve(self, ip: str) -> Optional[GeoResult]:
        try:
            reader = self._get_reader()
            resp = reader.city(ip)
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
            logger.debug(f"No geo data for {ip}")
            return None

    def resolve_batch(self, ips: list[str]) -> list[GeoResult]:
        results = []
        for ip in ips:
            geo = self.resolve(ip)
            if geo:
                results.append(geo)
        return results

    def close(self):
        if self._reader:
            self._reader.close()
            self._reader = None
