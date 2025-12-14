import math
import logging
from collections import Counter
from datetime import datetime, timezone

import numpy as np

logger = logging.getLogger(__name__)


def compute_entropy(counts: list[int]) -> float:
    total = sum(counts)
    if total == 0:
        return 0.0
    probs = [c / total for c in counts if c > 0]
    return -sum(p * math.log2(p) for p in probs)


def encode_time_of_day(timestamp_str: str) -> tuple[float, float]:
    try:
        dt = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        hour = dt.hour + dt.minute / 60
    except (ValueError, AttributeError):
        hour = 12.0
    angle = 2 * math.pi * hour / 24
    return math.sin(angle), math.cos(angle)


"""
WHAT IT DOES
Builds a 12-dim feature vector for a single IP from firewall events and abuse reputation.

HOW IT DOES IT
Filters events to the target IP, computes behavioral signals (request rate, path diversity,
method entropy, WAF action counts), merges in AbuseIPDB reputation fields, and encodes
the timestamp cyclically to avoid midnight discontinuity.

WHY I DID IT THIS WAY
All features are derivable from raw event dicts without preprocessing — keeps the pipeline
stateless so it can run per-poll-cycle without accumulating history.
"""
def extract_ip_features(
    ip: str,
    firewall_events: list[dict],
    abuse_data: dict,
    time_window_minutes: int = 15,
) -> np.ndarray:
    ip_events = [e for e in firewall_events if e.get("clientIP") == ip]

    request_rate = len(ip_events) / max(time_window_minutes, 1)

    paths = set(e.get("clientRequestPath", "/") for e in ip_events)
    unique_paths = len(paths)

    methods = [e.get("clientRequestHTTPMethodName", "GET") for e in ip_events]
    method_counts = list(Counter(methods).values())
    method_entropy = compute_entropy(method_counts)

    action_counts = Counter(e.get("action", "") for e in ip_events)
    block_count = action_counts.get("block", 0)
    challenge_count = action_counts.get("challenge", 0)
    js_challenge_count = action_counts.get("js_challenge", 0)

    abuse_score = abuse_data.get("abuse_score", 0) / 100.0
    total_reports = math.log1p(abuse_data.get("total_reports", 0))
    is_tor = float(abuse_data.get("is_tor", False))

    geo_anomaly = 0.0

    last_event_time = ip_events[-1].get("datetime", "") if ip_events else ""
    time_sin, time_cos = encode_time_of_day(last_event_time)

    return np.array([
        request_rate,
        unique_paths,
        method_entropy,
        block_count,
        challenge_count,
        js_challenge_count,
        abuse_score,
        total_reports,
        is_tor,
        geo_anomaly,
        time_sin,
        time_cos,
    ], dtype=np.float32)


def build_feature_matrix(
    ip_list: list[str],
    firewall_events: list[dict],
    abuse_map: dict[str, dict],
    time_window_minutes: int = 15,
) -> tuple[list[str], np.ndarray]:
    valid_ips = []
    feature_rows = []

    for ip in ip_list:
        abuse_data = abuse_map.get(ip, {})
        try:
            features = extract_ip_features(
                ip, firewall_events, abuse_data, time_window_minutes
            )
            feature_rows.append(features)
            valid_ips.append(ip)
        except Exception as e:
            logger.warning(f"Feature extraction failed for {ip}: {e}")

    if not feature_rows:
        return [], np.empty((0, 12), dtype=np.float32)

    matrix = np.stack(feature_rows)
    logger.info(f"Built feature matrix: {matrix.shape} for {len(valid_ips)} IPs")
    return valid_ips, matrix
