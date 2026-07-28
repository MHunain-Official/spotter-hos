"""Road routing via OSRM (shortest-path on the OSM road graph).

OSRM uses contraction hierarchies / Dijkstra-style search on the road network —
not straight-line geometry. Optional OpenRouteService key; haversine only as last resort.
"""

from __future__ import annotations

import math
from typing import Any

import requests
from django.conf import settings


class RoutingError(Exception):
    pass


def _haversine_miles(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 3958.8
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _fallback_route(points: list[dict[str, float]]) -> dict[str, Any]:
    """Last-resort straight line — only if all road routers fail."""
    mph = settings.ROUTING_FALLBACK_MPH
    geometry: list[list[float]] = []
    legs = []
    total_miles = 0.0
    total_hours = 0.0
    for i in range(len(points) - 1):
        a, b = points[i], points[i + 1]
        miles = _haversine_miles(a["lat"], a["lng"], b["lat"], b["lng"]) * 1.2
        hours = miles / mph if mph else miles / 55.0
        geometry.append([a["lng"], a["lat"]])
        legs.append({"miles": round(miles, 2), "duration_hours": round(hours, 3)})
        total_miles += miles
        total_hours += hours
    geometry.append([points[-1]["lng"], points[-1]["lat"]])
    return {
        "geometry": geometry,
        "legs": legs,
        "total_miles": round(total_miles, 2),
        "total_hours": round(total_hours, 3),
        "approximate": True,
        "provider": "haversine",
    }


def route_via_osrm(points: list[dict[str, float]]) -> dict[str, Any] | None:
    """
    Public OSRM router — follows real roads (A*/Dijkstra-family search on OSM graph).
    https://router.project-osrm.org
    """
    if len(points) < 2:
        return None

    coord_str = ";".join(f"{p['lng']},{p['lat']}" for p in points)
    url = (
        f"https://router.project-osrm.org/route/v1/driving/{coord_str}"
        f"?overview=full&geometries=geojson&steps=false"
    )
    try:
        resp = requests.get(url, timeout=45, headers={"User-Agent": settings.NOMINATIM_USER_AGENT})
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, ValueError):
        return None

    if data.get("code") != "Ok" or not data.get("routes"):
        return None

    route = data["routes"][0]
    geometry = route["geometry"]["coordinates"]  # [lng, lat][]
    legs = []
    for leg in route.get("legs") or []:
        legs.append(
            {
                "miles": round(leg.get("distance", 0) / 1609.344, 2),
                "duration_hours": round(leg.get("duration", 0) / 3600.0, 3),
            }
        )
    if not legs:
        return None

    return {
        "geometry": geometry,
        "legs": legs,
        "total_miles": round(sum(l["miles"] for l in legs), 2),
        "total_hours": round(sum(l["duration_hours"] for l in legs), 3),
        "approximate": False,
        "provider": "osrm",
    }


def route_via_ors(points: list[dict[str, float]]) -> dict[str, Any] | None:
    key = settings.ORS_API_KEY
    if not key:
        return None

    coords = [[p["lng"], p["lat"]] for p in points]
    headers = {"Authorization": key, "Content-Type": "application/json"}
    body = {"coordinates": coords}

    for profile in ("driving-hgv", "driving-car"):
        url = f"https://api.openrouteservice.org/v2/directions/{profile}/geojson"
        try:
            resp = requests.post(url, json=body, headers=headers, timeout=30)
            if resp.status_code >= 400:
                continue
            data = resp.json()
        except requests.RequestException:
            continue

        features = data.get("features") or []
        if not features:
            continue

        feat = features[0]
        geometry = feat["geometry"]["coordinates"]
        props = feat.get("properties", {})
        segments = props.get("segments") or []
        legs = []
        if segments:
            for seg in segments:
                legs.append(
                    {
                        "miles": round(seg.get("distance", 0) / 1609.344, 2),
                        "duration_hours": round(seg.get("duration", 0) / 3600.0, 3),
                    }
                )
        else:
            summary = props.get("summary") or {}
            n = max(1, len(points) - 1)
            meters = summary.get("distance", 0)
            seconds = summary.get("duration", 0)
            legs = [
                {
                    "miles": round((meters / 1609.344) / n, 2),
                    "duration_hours": round((seconds / 3600.0) / n, 3),
                }
                for _ in range(n)
            ]

        return {
            "geometry": geometry,
            "legs": legs,
            "total_miles": round(sum(l["miles"] for l in legs), 2),
            "total_hours": round(sum(l["duration_hours"] for l in legs), 3),
            "approximate": False,
            "provider": "ors",
        }
    return None


def route_points(points: list[dict[str, float]]) -> dict[str, Any]:
    """
    Prefer OpenRouteService when ORS_API_KEY is set (supports driving-hgv),
    then public OSRM, then straight-line fallback.
    """
    if settings.ORS_API_KEY:
        return route_via_ors(points) or route_via_osrm(points) or _fallback_route(points)
    return route_via_osrm(points) or route_via_ors(points) or _fallback_route(points)


def build_route(current: dict, pickup: dict, dropoff: dict) -> dict[str, Any]:
    points = [
        {"lat": current["lat"], "lng": current["lng"]},
        {"lat": pickup["lat"], "lng": pickup["lng"]},
        {"lat": dropoff["lat"], "lng": dropoff["lng"]},
    ]
    # Collapse zero-length first leg if current ~= pickup
    if _haversine_miles(current["lat"], current["lng"], pickup["lat"], pickup["lng"]) < 0.5:
        points = [
            {"lat": pickup["lat"], "lng": pickup["lng"]},
            {"lat": dropoff["lat"], "lng": dropoff["lng"]},
        ]
        result = route_points(points)
        if len(result["legs"]) == 1:
            result["legs"] = [
                {"miles": 0.0, "duration_hours": 0.0},
                result["legs"][0],
            ]
        return result

    return route_points(points)
