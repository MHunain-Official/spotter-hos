import { useState } from "react";
import {
  Box,
  Button,
  FormControlLabel,
  Stack,
  Switch,
  TextField,
  Typography,
  Slider,
  Alert,
  Chip,
} from "@mui/material";
import { DateTimePicker } from "@mui/x-date-pickers/DateTimePicker";
import dayjs, { Dayjs } from "dayjs";
import type { PlanTripRequest } from "../api/trips";

type Props = {
  loading: boolean;
  error: string | null;
  onSubmit: (payload: PlanTripRequest) => void;
};

const EXAMPLES = [
  {
    label: "Chicago → Dallas → Houston",
    current: "Chicago, IL",
    pickup: "Dallas, TX",
    dropoff: "Houston, TX",
  },
  {
    label: "LA → Phoenix → Denver",
    current: "Los Angeles, CA",
    pickup: "Phoenix, AZ",
    dropoff: "Denver, CO",
  },
  {
    label: "NYC → Philly → Atlanta",
    current: "New York, NY",
    pickup: "Philadelphia, PA",
    dropoff: "Atlanta, GA",
  },
] as const;

export default function TripPlanForm({ loading, error, onSubmit }: Props) {
  const [current, setCurrent] = useState("");
  const [pickup, setPickup] = useState("");
  const [dropoff, setDropoff] = useState("");
  const [cycleUsed, setCycleUsed] = useState(12);
  const [start, setStart] = useState<Dayjs | null>(dayjs().hour(6).minute(0).second(0));
  const [adverse, setAdverse] = useState(false);

  const canSubmit = current.trim() && pickup.trim() && dropoff.trim();

  return (
    <Box
      component="form"
      onSubmit={(e) => {
        e.preventDefault();
        if (!canSubmit) return;
        onSubmit({
          current_location: current.trim(),
          pickup_location: pickup.trim(),
          dropoff_location: dropoff.trim(),
          current_cycle_used_hours: cycleUsed,
          trip_start: start ? start.toISOString() : null,
          adverse_conditions: adverse,
          auto_34h_restart: true,
          home_terminal_tz: "America/Chicago",
        });
      }}
    >
      <Stack spacing={2.25}>
        <Box>
          <Typography variant="overline" sx={{ color: "primary.main" }}>
            Trip intake
          </Typography>
          <Typography variant="h3" sx={{ fontSize: { xs: 26, md: 32 }, mt: 0.5 }}>
            Build the haul
          </Typography>
          <Typography color="text.secondary" sx={{ mt: 0.75, maxWidth: 440 }}>
            Enter <strong>any</strong> city or address for current, pickup, and dropoff.
            We geocode + route the road path, then fill HOS daily logs.
          </Typography>
        </Box>

        {error && <Alert severity="error">{error}</Alert>}

        <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1 }}>
          <Typography variant="caption" sx={{ width: "100%", color: "text.secondary" }}>
            Optional quick examples:
          </Typography>
          {EXAMPLES.map((ex) => (
            <Chip
              key={ex.label}
              label={ex.label}
              size="small"
              variant="outlined"
              onClick={() => {
                setCurrent(ex.current);
                setPickup(ex.pickup);
                setDropoff(ex.dropoff);
              }}
              sx={{ cursor: "pointer" }}
            />
          ))}
        </Box>

        <TextField
          label="Current location"
          placeholder="e.g. Kansas City, MO or 123 Main St, Omaha, NE"
          value={current}
          onChange={(e) => setCurrent(e.target.value)}
          required
          fullWidth
          helperText="Where the driver is now (any place Nominatim can resolve)"
        />
        <Box
          sx={{
            display: "grid",
            gap: 1.5,
            gridTemplateColumns: { xs: "1fr", sm: "1fr 1fr" },
          }}
        >
          <TextField
            label="Pickup location"
            placeholder="e.g. warehouse or city"
            value={pickup}
            onChange={(e) => setPickup(e.target.value)}
            required
            fullWidth
            helperText="Load point — any address/city"
          />
          <TextField
            label="Dropoff location"
            placeholder="e.g. destination yard or city"
            value={dropoff}
            onChange={(e) => setDropoff(e.target.value)}
            required
            fullWidth
            helperText="Unload point — any address/city"
          />
          <DateTimePicker
            label="Trip start"
            value={start}
            onChange={setStart}
            slotProps={{ textField: { fullWidth: true } }}
          />
          <Box sx={{ px: 0.5, pt: 0.5 }}>
            <Typography variant="caption" sx={{ fontWeight: 700, letterSpacing: "0.08em" }}>
              CYCLE USED · {cycleUsed.toFixed(1)} / 70 H
            </Typography>
            <Slider
              value={cycleUsed}
              min={0}
              max={70}
              step={0.5}
              onChange={(_, v) => setCycleUsed(v as number)}
              valueLabelDisplay="auto"
              sx={{ color: "secondary.main", mt: 1 }}
            />
            {cycleUsed >= 60 && (
              <Alert severity="warning" sx={{ mt: 1.25 }}>
                Cycle pressure: only {(70 - cycleUsed).toFixed(1)}h left in the 70/8 window.
                Planning may insert a 34h restart if on-duty demand exceeds remaining hours.
              </Alert>
            )}
          </Box>
        </Box>

        <FormControlLabel
          control={
            <Switch
              checked={adverse}
              onChange={(e) => setAdverse(e.target.checked)}
              color="primary"
            />
          }
          label="Adverse conditions (+2h drive / window)"
        />

        <Button
          type="submit"
          variant="contained"
          size="large"
          disabled={loading || !canSubmit}
          sx={{ alignSelf: { sm: "flex-start" }, minWidth: 220 }}
        >
          {loading ? "Routing & planning…" : "Plan route & logs"}
        </Button>
      </Stack>
    </Box>
  );
}
