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
} from "@mui/material";
import { DateTimePicker } from "@mui/x-date-pickers/DateTimePicker";
import dayjs, { Dayjs } from "dayjs";
import type { PlanTripRequest } from "../api/trips";

type Props = {
  loading: boolean;
  error: string | null;
  onSubmit: (payload: PlanTripRequest) => void;
};

export default function TripPlanForm({ loading, error, onSubmit }: Props) {
  const [current, setCurrent] = useState("Chicago, IL");
  const [pickup, setPickup] = useState("Dallas, TX");
  const [dropoff, setDropoff] = useState("Houston, TX");
  const [cycleUsed, setCycleUsed] = useState(12);
  const [start, setStart] = useState<Dayjs | null>(dayjs().hour(6).minute(0).second(0));
  const [adverse, setAdverse] = useState(false);

  return (
    <Box
      component="form"
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit({
          current_location: current,
          pickup_location: pickup,
          dropoff_location: dropoff,
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
          <Typography color="text.secondary" sx={{ mt: 0.75, maxWidth: 420 }}>
            Locations + cycle hours in. Road route, rests, fuel, and ELD sheets out.
          </Typography>
        </Box>

        {error && <Alert severity="error">{error}</Alert>}

        <TextField
          label="Current location"
          value={current}
          onChange={(e) => setCurrent(e.target.value)}
          required
          fullWidth
        />
        <Box
          sx={{
            display: "grid",
            gap: 1.5,
            gridTemplateColumns: { xs: "1fr", sm: "1fr 1fr" },
          }}
        >
          <TextField
            label="Pickup"
            value={pickup}
            onChange={(e) => setPickup(e.target.value)}
            required
            fullWidth
          />
          <TextField
            label="Dropoff"
            value={dropoff}
            onChange={(e) => setDropoff(e.target.value)}
            required
            fullWidth
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
          disabled={loading}
          sx={{ alignSelf: { sm: "flex-start" }, minWidth: 220 }}
        >
          {loading ? "Routing & planning…" : "Plan route & logs"}
        </Button>
      </Stack>
    </Box>
  );
}
