import type { DailyLog } from "../../api/trips";
import "./DailyLogSheet.css";

type Props = {
  log: DailyLog;
  tz?: string;
  carrierName?: string;
  officeAddress?: string;
  homeTerminal?: string;
  vehicleId?: string;
};

const ROW_ORDER = ["OFF", "SB", "D", "ON"] as const;
const ROW_LABELS: Record<string, string> = {
  OFF: "1. Off Duty",
  SB: "2. Sleeper Berth",
  D: "3. Driving",
  ON: "4. On Duty (not driving)",
};

/** Pixel-faithful Drivers Daily Log matching blank-paper-log.png */
export default function DailyLogSheet({
  log,
  tz = "America/Chicago",
  carrierName = "RouteLog Demo Carrier",
  officeAddress = "100 Dispatch Way, Chicago, IL",
  homeTerminal = `Home terminal · ${tz}`,
  vehicleId = "UNIT-RL-001 / TRL-4821 IL",
}: Props) {
  const [year, month, day] = log.date.split("-");
  const totals = log.totals;
  const sum =
    (totals.off_duty || 0) + (totals.sleeper || 0) + (totals.driving || 0) + (totals.on_duty || 0);
  const recap = log.recap || {};

  // SVG grid geometry
  const W = 920;
  const labelW = 128;
  const totalsW = 56;
  const gridX = labelW;
  const gridW = W - labelW - totalsW;
  const headerH = 22;
  const rowH = 28;
  const gridH = rowH * 4;
  const H = headerH + gridH + 4;
  const hourW = gridW / 24;

  const yForStatus = (status: string) => {
    const idx = ROW_ORDER.indexOf(status as (typeof ROW_ORDER)[number]);
    return headerH + (idx < 0 ? 0 : idx) * rowH + rowH / 2;
  };
  const xForHour = (h: number) => gridX + Math.min(24, Math.max(0, h)) * hourW;

  /** One status at a time: merge, drop zero-length ghosts, never draw parallel lines. */
  const normalizeSegments = (raw: typeof log.segments) => {
    const eps = 1e-6;
    const cleaned = raw
      .map((seg) => {
        let start = Math.min(24, Math.max(0, Number(seg.start_hour) || 0));
        let end = Math.min(24, Math.max(0, Number(seg.end_hour) || 0));
        // Midnight wrap only: evening → 0 means end-of-day, not a full-day ghost
        if (end + eps < start && end <= eps) end = 24;
        const status = (ROW_ORDER as readonly string[]).includes(seg.status)
          ? seg.status
          : "OFF";
        return { ...seg, status, start_hour: start, end_hour: end };
      })
      .filter((seg) => seg.end_hour > seg.start_hour + eps)
      .sort((a, b) => a.start_hour - b.start_hour || a.end_hour - b.end_hour);

    // Later segments win on overlap
    let pieces = cleaned.map((s) => ({ ...s }));
    const resolved: typeof pieces = [];
    for (const seg of pieces) {
      const next: typeof pieces = [];
      for (const p of resolved) {
        if (p.end_hour <= seg.start_hour + eps || p.start_hour >= seg.end_hour - eps) {
          next.push(p);
          continue;
        }
        if (p.start_hour < seg.start_hour - eps) {
          next.push({ ...p, end_hour: seg.start_hour });
        }
        if (p.end_hour > seg.end_hour + eps) {
          next.push({ ...p, start_hour: seg.end_hour });
        }
      }
      next.push(seg);
      resolved.length = 0;
      resolved.push(...next.sort((a, b) => a.start_hour - b.start_hour));
    }
    pieces = resolved;

    // Fill gaps with OFF so the polyline stays continuous
    const filled: typeof pieces = [];
    let cursor = 0;
    for (const seg of pieces) {
      if (seg.start_hour > cursor + eps) {
        filled.push({
          status: "OFF",
          start_hour: cursor,
          end_hour: seg.start_hour,
          remark: "Off duty",
        });
      }
      filled.push({ ...seg, start_hour: Math.max(cursor, seg.start_hour) });
      cursor = Math.max(cursor, seg.end_hour);
    }
    if (cursor < 24 - eps) {
      filled.push({
        status: "OFF",
        start_hour: cursor,
        end_hour: 24,
        remark: "Off duty",
      });
    }

    const merged: typeof filled = [];
    for (const seg of filled) {
      if (seg.end_hour <= seg.start_hour + eps) continue;
      const last = merged[merged.length - 1];
      if (last && last.status === seg.status && Math.abs(last.end_hour - seg.start_hour) < 1e-4) {
        last.end_hour = seg.end_hour;
      } else {
        merged.push({ ...seg });
      }
    }
    return merged;
  };

  const segs = normalizeSegments(log.segments);
  // Single continuous polyline: horizontal on a row, vertical only at status changes
  const pathParts: string[] = [];
  segs.forEach((seg, i) => {
    const y = yForStatus(seg.status);
    const x0 = xForHour(seg.start_hour);
    const x1 = xForHour(seg.end_hour);
    if (i === 0) {
      pathParts.push(`M ${x0} ${y}`);
    } else {
      pathParts.push(`L ${x0} ${y}`);
    }
    pathParts.push(`L ${x1} ${y}`);
  });

  const hourLabels = [
    "Mid",
    "1",
    "2",
    "3",
    "4",
    "5",
    "6",
    "7",
    "8",
    "9",
    "10",
    "11",
    "Noon",
    "1",
    "2",
    "3",
    "4",
    "5",
    "6",
    "7",
    "8",
    "9",
    "10",
    "11",
  ];

  const totalByStatus: Record<string, number> = {
    OFF: totals.off_duty || 0,
    SB: totals.sleeper || 0,
    D: totals.driving || 0,
    ON: totals.on_duty || 0,
  };

  return (
    <div className="paper-log" role="document" aria-label={`Drivers Daily Log ${log.date}`}>
      {/* Header */}
      <div className="paper-log__header">
        <div className="paper-log__title">Drivers Daily Log (24 hours)</div>
        <div className="paper-log__date">
          <span className="paper-log__date-box">{month}</span>
          <span>/</span>
          <span className="paper-log__date-box">{day}</span>
          <span>/</span>
          <span className="paper-log__date-box paper-log__date-box--year">{year}</span>
          <div className="paper-log__date-labels">
            <span>(month)</span>
            <span>(day)</span>
            <span>(year)</span>
          </div>
        </div>
        <div className="paper-log__filing">
          Original — File at home terminal.
          <br />
          Duplicate — Driver retains in his/her possession for 8 days.
        </div>
      </div>

      {/* From / To */}
      <div className="paper-log__fromto">
        <div className="paper-log__line-field">
          <span>From:</span>
          <span className="paper-log__underline">{log.from_location || "—"}</span>
        </div>
        <div className="paper-log__line-field">
          <span>To:</span>
          <span className="paper-log__underline">{log.to_location || "—"}</span>
        </div>
      </div>

      {/* Miles + vehicle */}
      <div className="paper-log__meta-row">
        <div className="paper-log__box">
          <div className="paper-log__box-value">{log.total_miles_driving.toFixed(1)}</div>
          <div className="paper-log__box-label">Total Miles Driving Today</div>
        </div>
        <div className="paper-log__box">
          <div className="paper-log__box-value">{log.total_miles_driving.toFixed(1)}</div>
          <div className="paper-log__box-label">Total Mileage Today</div>
        </div>
        <div className="paper-log__box paper-log__box--wide">
          <div className="paper-log__box-value paper-log__box-value--sm">{vehicleId}</div>
          <div className="paper-log__box-label">
            Truck/Tractor and Trailer Numbers or License Plate(s)/State (show each unit)
          </div>
        </div>
      </div>

      {/* Carrier lines */}
      <div className="paper-log__carrier">
        <div className="paper-log__line-field">
          <span className="paper-log__underline">{carrierName}</span>
          <span className="paper-log__field-caption">Name of Carrier or Carriers</span>
        </div>
        <div className="paper-log__line-field">
          <span className="paper-log__underline">{officeAddress}</span>
          <span className="paper-log__field-caption">Main Office Address</span>
        </div>
        <div className="paper-log__line-field">
          <span className="paper-log__underline">{homeTerminal}</span>
          <span className="paper-log__field-caption">Home Terminal Address</span>
        </div>
      </div>

      {/* Duty grid */}
      <div className="paper-log__grid-wrap">
        <svg
          className="paper-log__grid"
          viewBox={`0 0 ${W} ${H}`}
          width="100%"
          role="img"
          aria-label="24-hour duty status graph grid"
        >
          {/* Black time header */}
          <rect x={gridX} y={0} width={gridW} height={headerH} fill="#111" />
          {hourLabels.map((label, h) => (
            <text
              key={`h-${h}`}
              x={gridX + h * hourW + hourW / 2}
              y={15}
              textAnchor="middle"
              fill="#fff"
              fontSize={h === 0 || h === 12 ? 8 : 9}
              fontFamily="IBM Plex Mono, monospace"
            >
              {label}
            </text>
          ))}
          <text
            x={gridX + gridW - 2}
            y={15}
            textAnchor="end"
            fill="#fff"
            fontSize={8}
            fontFamily="IBM Plex Mono, monospace"
          >
            Mid
          </text>

          {/* Total Hours header */}
          <rect x={gridX + gridW} y={0} width={totalsW} height={headerH} fill="#111" />
          <text
            x={gridX + gridW + totalsW / 2}
            y={14}
            textAnchor="middle"
            fill="#fff"
            fontSize={8}
            fontFamily="IBM Plex Mono, monospace"
          >
            Total
          </text>

          {/* Rows */}
          {ROW_ORDER.map((code, i) => {
            const y0 = headerH + i * rowH;
            return (
              <g key={code}>
                <rect
                  x={0}
                  y={y0}
                  width={W}
                  height={rowH}
                  fill={i % 2 === 0 ? "#fafafa" : "#fff"}
                  stroke="#222"
                  strokeWidth={0.6}
                />
                <text
                  x={6}
                  y={y0 + rowH / 2 + 4}
                  fontSize={10}
                  fontFamily="Manrope, sans-serif"
                  fill="#111"
                >
                  {ROW_LABELS[code]}
                </text>
                {/* hour + 15-min ticks */}
                {Array.from({ length: 24 }).map((_, h) => (
                  <g key={`${code}-${h}`}>
                    <line
                      x1={gridX + h * hourW}
                      x2={gridX + h * hourW}
                      y1={y0}
                      y2={y0 + rowH}
                      stroke="#333"
                      strokeWidth={h % 6 === 0 ? 1.1 : 0.5}
                    />
                    {[1, 2, 3].map((q) => (
                      <line
                        key={q}
                        x1={gridX + h * hourW + (q * hourW) / 4}
                        x2={gridX + h * hourW + (q * hourW) / 4}
                        y1={y0 + rowH * 0.35}
                        y2={y0 + rowH}
                        stroke="#999"
                        strokeWidth={0.4}
                      />
                    ))}
                  </g>
                ))}
                <line
                  x1={gridX + gridW}
                  x2={gridX + gridW}
                  y1={y0}
                  y2={y0 + rowH}
                  stroke="#222"
                  strokeWidth={1}
                />
                <text
                  x={gridX + gridW + totalsW / 2}
                  y={y0 + rowH / 2 + 4}
                  textAnchor="middle"
                  fontSize={11}
                  fontFamily="IBM Plex Mono, monospace"
                  fontWeight={600}
                >
                  {totalByStatus[code].toFixed(2)}
                </text>
              </g>
            );
          })}

          {/* Outer border */}
          <rect
            x={gridX}
            y={headerH}
            width={gridW}
            height={gridH}
            fill="none"
            stroke="#111"
            strokeWidth={1.4}
          />

          {/* Duty line — one continuous stroke, never parallel statuses */}
          <path
            d={pathParts.join(" ")}
            stroke="#111"
            strokeWidth={2.2}
            fill="none"
            strokeLinejoin="round"
            strokeLinecap="butt"
          />

          {/* =24 check under totals */}
          <text
            x={gridX + gridW + totalsW / 2}
            y={H - 1}
            textAnchor="middle"
            fontSize={9}
            fontFamily="IBM Plex Mono, monospace"
          >
            ={sum.toFixed(1)}
          </text>
        </svg>
      </div>

      {/* Remarks */}
      <div className="paper-log__remarks">
        <div className="paper-log__remarks-title">Remarks</div>
        <div className="paper-log__remarks-body">
          <div className="paper-log__shipping">
            <div className="paper-log__line-field">
              <span className="paper-log__ship-label">Shipping Documents:</span>
            </div>
            <div className="paper-log__line-field">
              <span>DVL or Manifest No. or</span>
              <span className="paper-log__underline">RL-{log.date.replace(/-/g, "")}</span>
            </div>
            <div className="paper-log__line-field">
              <span>Shipper &amp; Commodity</span>
              <span className="paper-log__underline">General freight</span>
            </div>
          </div>
          <ul className="paper-log__remark-list">
            {log.remarks.map((r, i) => (
              <li key={`${r.time}-${i}`}>
                <strong>{r.time}</strong> {r.place ? `· ${r.place}` : ""} — {r.note}
              </li>
            ))}
          </ul>
        </div>
        <p className="paper-log__remarks-note">
          Enter name of place you reported and where released from work and when and where each
          change of duty occurred. Use time standard of home terminal ({tz}).
        </p>
      </div>

      {/* Recap */}
      <div className="paper-log__recap">
        <div className="paper-log__recap-left">
          <div className="paper-log__recap-heading">Recap: Complete at end of day</div>
          <div className="paper-log__recap-today">
            On duty hours today, Total lines 3 &amp; 4
            <span className="paper-log__recap-value">
              {Number(recap.on_duty_today ?? totals.driving + totals.on_duty).toFixed(2)}
            </span>
          </div>
        </div>

        <div className="paper-log__recap-cols">
          <div className="paper-log__recap-col">
            <div className="paper-log__recap-col-title">70 Hour / 8 Day Drivers</div>
            <div className="paper-log__recap-row">
              <span>
                <strong>A.</strong> Total hours on duty last 7 days including today
              </span>
              <span className="paper-log__recap-value">
                {Number(recap.a_70_last_7_incl_today ?? recap.a_last_7_including_today ?? 0).toFixed(2)}
              </span>
            </div>
            <div className="paper-log__recap-row">
              <span>
                <strong>B.</strong> Total hours available tomorrow (70 hr. minus A*)
              </span>
              <span className="paper-log__recap-value">
                {Number(recap.b_70_available_tomorrow ?? recap.b_available_tomorrow ?? 0).toFixed(2)}
              </span>
            </div>
            <div className="paper-log__recap-row">
              <span>
                <strong>C.</strong> Total hours on duty last 8 days including today
              </span>
              <span className="paper-log__recap-value">
                {Number(recap.c_70_last_8_incl_today ?? recap.cycle_used_8_day ?? 0).toFixed(2)}
              </span>
            </div>
          </div>

          <div className="paper-log__recap-col paper-log__recap-col--muted">
            <div className="paper-log__recap-col-title">60 Hour / 7 Day Drivers</div>
            <div className="paper-log__recap-row">
              <span>
                <strong>A.</strong> Total hours on duty last 6 days including today
              </span>
              <span className="paper-log__recap-value">
                {Number(recap.a_60_last_6_incl_today ?? 0).toFixed(2)}
              </span>
            </div>
            <div className="paper-log__recap-row">
              <span>
                <strong>B.</strong> Total hours available tomorrow (60 hr. minus A*)
              </span>
              <span className="paper-log__recap-value">
                {Number(recap.b_60_available_tomorrow ?? 0).toFixed(2)}
              </span>
            </div>
            <div className="paper-log__recap-row">
              <span>
                <strong>C.</strong> Total hours on duty last 7 days including today
              </span>
              <span className="paper-log__recap-value">
                {Number(recap.c_60_last_7_incl_today ?? 0).toFixed(2)}
              </span>
            </div>
          </div>
        </div>

        <div className="paper-log__recap-note">
          *If you took 34 consecutive hours off duty you have 60/70 hours available.
        </div>
      </div>
    </div>
  );
}
