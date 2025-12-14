import os
from dotenv import load_dotenv

load_dotenv()

CF_API_TOKEN = os.getenv("CF_API_TOKEN")
CF_ZONE_ID = os.getenv("CF_ZONE_ID")
ABUSEIPDB_API_KEY = os.getenv("ABUSEIPDB_API_KEY")

FETCH_INTERVAL_SEC = 300
CONFIDENCE_THRESHOLD = 0.85

GEOIP_DB_PATH = os.getenv("GEOIP_DB_PATH", "data/GeoLite2-City.mmdb")
MODEL_CHECKPOINT_DIR = "models/checkpoints"
