import { useEffect, useMemo } from "react";
import { MapContainer, TileLayer, Polyline, Marker, Popup, useMap } from "react-leaflet";
import type { TripPlan, TripStop } from "../../api/trips";
import { createStopIcon } from "./stopIcons";
import "leaflet/dist/leaflet.css";

function FitBounds({ geometry, stops }: { geometry: number[][]; stops: TripStop[] }) {
  const map = useMap();
  useEffect(() => {
    const pts: [number, number][] = [];
    geometry.forEach(([lng, lat]) => pts.push([lat, lng]));
    stops.forEach((s) => pts.push([s.lat, s.lng]));
    if (pts.length >= 2) {
      map.fitBounds(pts, { padding: [48, 48], maxZoom: 10 });
    }
  }, [geometry, stops, map]);
  return null;
}

export default function RouteMap({ trip }: { trip: TripPlan }) {
  const positions = useMemo(
    () => trip.route.geometry.map(([lng, lat]) => [lat, lng] as [number, number]),
    [trip.route.geometry],
  );
  const center = positions[Math.floor(positions.length / 2)] || ([39.5, -98.35] as [number, number]);
  const pointCount = positions.length;

  return (
    <div style={{ position: "relative", height: "100%", width: "100%" }}>
      <MapContainer
        center={center}
        zoom={5}
        style={{ height: "100%", width: "100%", minHeight: 380 }}
        scrollWheelZoom
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a>'
          url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png"
        />
        {positions.length > 1 && (
          <Polyline
            positions={positions}
            pathOptions={{ color: "#E23D28", weight: 5, opacity: 0.92, lineJoin: "round" }}
          />
        )}
        {trip.stops.map((stop, idx) => (
          <Marker
            key={`${stop.type}-${idx}-${stop.arrive_at}`}
            position={[stop.lat, stop.lng]}
            icon={createStopIcon(stop.type)}
          >
            <Popup>
              <strong>{stop.label}</strong>
              <br />
              {stop.type.toUpperCase()} · {stop.duration_hours}h
            </Popup>
          </Marker>
        ))}
        <FitBounds geometry={trip.route.geometry} stops={trip.stops} />
      </MapContainer>
      <div
        style={{
          position: "absolute",
          left: 12,
          bottom: 12,
          zIndex: 1000,
          background: "rgba(255,255,255,0.92)",
          border: "2px solid #0B1F33",
          padding: "8px 12px",
          fontFamily: "IBM Plex Mono, monospace",
          fontSize: 11,
          color: "#0B1F33",
        }}
      >
        {trip.approximate_routing
          ? "Straight-line fallback"
          : `Road route · ${pointCount.toLocaleString()} vertices (${(
              trip.routing_provider ||
              (trip.summary?.routing_provider as string | undefined) ||
              "road"
            ).toUpperCase()})`}
      </div>
    </div>
  );
}
