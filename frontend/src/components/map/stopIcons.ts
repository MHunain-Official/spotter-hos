import L from "leaflet";

const colors: Record<string, { bg: string; fg: string }> = {
  origin: { bg: "#0B1F33", fg: "#FFFFFF" },
  pickup: { bg: "#E23D28", fg: "#FFFFFF" },
  dropoff: { bg: "#1F7A4C", fg: "#FFFFFF" },
  fuel: { bg: "#C45C12", fg: "#FFFFFF" },
  rest: { bg: "#1A5F7A", fg: "#FFFFFF" },
};

const labels: Record<string, string> = {
  origin: "A",
  pickup: "P",
  dropoff: "D",
  fuel: "F",
  rest: "R",
};

export function createStopIcon(type: string) {
  const c = colors[type] || colors.pickup;
  const letter = labels[type] || "?";
  const radius = type === "pickup" || type === "dropoff" ? "3px" : "50%";
  const html = `
    <div style="
      width:34px;height:34px;border-radius:${radius};
      background:${c.bg};color:${c.fg};
      display:flex;align-items:center;justify-content:center;
      font-family:Syne,sans-serif;font-weight:800;font-size:13px;
      border:2px solid #fff;box-shadow:0 2px 0 rgba(11,31,51,.35);
    ">${letter}</div>`;
  return L.divIcon({
    className: "routelog-marker",
    html,
    iconSize: [34, 34],
    iconAnchor: [17, 17],
    popupAnchor: [0, -16],
  });
}
