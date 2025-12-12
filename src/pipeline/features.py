"""
Feature extraction pipeline.

Transforms raw Cloudflare firewall events + AbuseIPDB enrichment
into feature vectors for the DDoS classifier.
"""

import math
import logging
from collections import Counter
from datetime import datetime, timezone

import numpy as np

logger = logging.getLogger(__name__)


def compute_entropy(counts: list[int]) -> float:
    """Shannon entropy of a frequency distribution."""
    total = sum(counts)
    if total == 0:
        return 0.0
    probs = [c / total for c in counts if c > 0]
    return -sum(p * math.log2(p) for p in probs)


def encode_time_of_day(timestamp_str: str) -> tuple[float, float]:
    """Cyclical encoding of hour-of-day as (sin, cos) pair."""
    try:
        dt = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        hour = dt.hour + dt.minute / 60
    except (ValueError, AttributeError):
        hour = 12.0
    angle = 2 * math.pi * hour / 24
    return math.sin(angle), math.cos(angle)


def extract_ip_features(
    ip: str,
    firewall_events: list[dict],
    abuse_data: dict,
    time_window_minutes: int = 15,
) -> np.ndarray:
    """
    Build a feature vector for a single IP.

    Features (12-dim):
        0: request_rate (events per minute)
        1: unique_paths (number of distinct paths targeted)
        2: method_entropy (HTTP method distribution entropy)
        3: block_count (times blocked by WAF)
        4: challenge_count (times challenged)
        5: js_challenge_count
        6: abuse_score (AbuseIPDB confidence 0-100, normalized)
        7: total_reports (AbuseIPDB, log-scaled)
        8: is_tor (binary)
        9: geo_anomaly (placeholder - 0.0 for now)
        10: time_sin (cyclical hour encoding)
        11: time_cos (cyclical hour encoding)
    """
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
    """
    Build feature matrix for a batch of IPs.

    Returns:
        (ip_list, feature_matrix) where feature_matrix is (N, 12)
    """
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
