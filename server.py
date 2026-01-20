import asyncio
import logging
import time

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.ingestion.abuseipdb import AbuseIPDBClient
from src.geo.resolver import GeoResolver

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Crossfire API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

attack_cache: dict = {"attacks": [], "last_updated": 0}
POLL_INTERVAL = 300
_poll_task = None


async def poll_attacks():
    client = AbuseIPDBClient()
    geo = GeoResolver()

    while True:
        try:
            logger.info("Polling AbuseIPDB blacklist...")
            blacklist = await client.get_blacklist(confidence_minimum=85, limit=200)

            ips = [e["ip"] for e in blacklist]
            locations = await geo.resolve_batch_async(ips)
            loc_map = {loc.ip: loc for loc in locations}

            attacks = []
            for entry in blacklist:
                loc = loc_map.get(entry["ip"])
                if not loc:
                    continue
                attacks.append({
                    "ip": entry["ip"],
                    "lat": loc.latitude,
                    "lng": loc.longitude,
                    "city": loc.city,
                    "country": loc.country,
                    "country_code": loc.country_code,
                    "abuse_score": entry["abuse_score"],
                    "last_reported": entry.get("last_reported"),
                })

            attack_cache["attacks"] = attacks
            attack_cache["last_updated"] = time.time()
            logger.info(f"Cached {len(attacks)} geo-resolved attacks")

        except Exception as e:
            logger.exception(f"Poll error: {e}")

        await asyncio.sleep(POLL_INTERVAL)


@app.on_event("startup")
async def startup():
    global _poll_task
    _poll_task = asyncio.create_task(poll_attacks())


@app.get("/api/attacks")
async def get_attacks():
    return {
        "count": len(attack_cache["attacks"]),
        "last_updated": attack_cache["last_updated"],
        "attacks": attack_cache["attacks"],
    }


@app.get("/api/health")
async def health():
    return {"status": "ok", "cached_attacks": len(attack_cache["attacks"])}
