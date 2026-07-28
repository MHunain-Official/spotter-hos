"""Geocoding via Nominatim (OSM)."""

from __future__ import annotations

import time
from typing import Any

import requests
from django.conf import settings


class GeocodeError(Exception):
    pass


_last_nominatim_call = 0.0


def geocode(query: str) -> dict[str, Any]:
    """Return {label, lat, lng} for an address / place string."""
    global _last_nominatim_call
    q = (query or "").strip()
    if not q:
        raise GeocodeError("Empty location")

    # Nominatim usage policy: max 1 req/sec
    elapsed = time.time() - _last_nominatim_call
    if elapsed < 1.05:
        time.sleep(1.05 - elapsed)

    url = "https://nominatim.openstreetmap.org/search"
    params = {
        "q": q,
        "format": "json",
        "limit": 1,
        # Prefer US results for CMV / FMCSA assessment, but still accept full query text
        "countrycodes": "us",
        "addressdetails": 1,
    }
    headers = {"User-Agent": settings.NOMINATIM_USER_AGENT}
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=20)
        _last_nominatim_call = time.time()
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as exc:
        raise GeocodeError(f"Geocoding failed for '{q}': {exc}") from exc

    if not data:
        # Retry without country filter for Canada/Mexico edge cases or odd queries
        try:
            resp = requests.get(
                url,
                params={"q": q, "format": "json", "limit": 1},
                headers=headers,
                timeout=20,
            )
            _last_nominatim_call = time.time()
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as exc:
            raise GeocodeError(f"Geocoding failed for '{q}': {exc}") from exc

    if not data:
        raise GeocodeError(
            f"No results for '{q}'. Try a clearer city/state or full street address."
        )

    hit = data[0]
    return {
        "label": hit.get("display_name", q),
        "lat": float(hit["lat"]),
        "lng": float(hit["lon"]),
        "query": q,
    }
