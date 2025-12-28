# Crossfire

Real-time DDoS attack visualization map.

## Architecture

- **Data Ingestion** — Cloudflare Analytics API + AbuseIPDB for IP reputation
- **Classification** — PyTorch model scoring IPs by DDoS confidence
- **Geolocation** — MaxMind GeoLite2 for IP → coordinate mapping
- **Visualization** — Interactive 3D globe (cobe/Three.js) with live attack arcs

## Setup

```bash
cp .env.example .env
# fill in your API keys

pip install -r requirements.txt
cd frontend && npm install
```

## Project Structure

```
src/
├── ingestion/       # Cloudflare + AbuseIPDB data fetchers
├── model/           # PyTorch DDoS classifier
├── geo/             # IP geolocation resolver
└── pipeline/        # Feature extraction and preprocessing
frontend/
└── src/components/  # Globe visualization
```
