import axios from "axios";

const API_BASE = import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000/api/v1";

export type PlanTripRequest = {
  current_location: string;
  pickup_location: string;
  dropoff_location: string;
  current_cycle_used_hours: number;
  trip_start?: string | null;
  adverse_conditions?: boolean;
  auto_34h_restart?: boolean;
  home_terminal_tz?: string;
};

export type TripStop = {
  type: string;
  label: string;
  lat: number;
  lng: number;
  arrive_at: string;
  depart_at: string;
  duration_hours: number;
};

export type DailyLog = {
  date: string;
  from_location: string;
  to_location: string;
  total_miles_driving: number;
  segments: Array<{
    status: string;
    start_hour: number;
    end_hour: number;
    remark: string;
  }>;
  totals: {
    off_duty: number;
    sleeper: number;
    driving: number;
    on_duty: number;
  };
  remarks: Array<{ time: string; place: string; note: string }>;
  recap: {
    on_duty_today?: number;
    a_70_last_7_incl_today?: number;
    b_70_available_tomorrow?: number;
    c_70_last_8_incl_today?: number;
    a_60_last_6_incl_today?: number;
    b_60_available_tomorrow?: number;
    c_60_last_7_incl_today?: number;
    a_last_7_including_today?: number;
    b_available_tomorrow?: number;
    cycle_used_8_day?: number;
    [key: string]: number | undefined;
  };
};

export type TripPlan = {
  id: string;
  status: string;
  pdf_status: string;
  pdf_url?: string | null;
  approximate_routing: boolean;
  routing_provider?: string | null;
  adverse_conditions: boolean;
  home_terminal_tz: string;
  summary: Record<string, unknown>;
  route: { geometry: number[][]; legs: unknown[] };
  stops: TripStop[];
  daily_logs: DailyLog[];
  inputs: Record<string, unknown>;
};

export async function planTrip(body: PlanTripRequest): Promise<TripPlan> {
  const { data } = await axios.post<TripPlan>(`${API_BASE}/trips/plan/`, body);
  return data;
}

/** Absolute URL for downloading the trip PDF report. */
export function tripPdfUrl(tripId: string): string {
  return `${API_BASE}/trips/${tripId}/pdf/`;
}
