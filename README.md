# Crossfire

Real-time DDoS attack visualization map.

## Architecture

- **Data Ingestion** — Cloudflare Analytics API + AbuseIPDB for IP reputation
- **Classification** — PyTorch model scoring IPs by DDoS confidence
- **Geolocation** — MaxMind GeoLite2 / ip-api.com for IP → coordinate mapping
- **Backend** — FastAPI server with periodic polling and attack caching
- **Visualization** — Interactive 3D globe (cobe) with live attack markers

## Setup

```bash
cp .env.example .env
# fill in your API keys

pip install -r requirements.txt
cd frontend && npm install
```

## Running

```bash
# Start the API server
uvicorn server:app --host 0.0.0.0 --port 8000

# Start the frontend (in another terminal)
cd frontend && npm run dev
```

## Project Structure

```
src/
├── ingestion/       # Cloudflare + AbuseIPDB data fetchers
├── model/           # PyTorch DDoS classifier
├── geo/             # IP geolocation resolver
└── pipeline/        # Feature extraction and preprocessing
server.py            # FastAPI backend
frontend/
└── src/
    ├── app/         # Next.js pages
    ├── components/  # Globe, AttackFeed, StatsBar
    └── hooks/       # Data fetching hooks
```
