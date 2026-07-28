import { useMemo, useState } from "react";
import {
  AppBar,
  Box,
  Button,
  Container,
  Stack,
  Tab,
  Tabs,
  Toolbar,
  Typography,
  Paper,
  Stepper,
  Step,
  StepLabel,
  Alert,
} from "@mui/material";
import { DataGrid } from "@mui/x-data-grid";
import type { GridColDef } from "@mui/x-data-grid";
import { LocalizationProvider } from "@mui/x-date-pickers/LocalizationProvider";
import { AdapterDayjs } from "@mui/x-date-pickers/AdapterDayjs";
import DownloadIcon from "@mui/icons-material/Download";
import TripPlanForm from "./components/TripPlanForm";
import RouteMap from "./components/map/RouteMap";
import DailyLogSheet from "./components/logs/DailyLogSheet";
import { planTrip, tripPdfUrl, type PlanTripRequest, type TripPlan } from "./api/trips";

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <Box>
      <div className="routelog-metric-label">{label}</div>
      <div className="routelog-metric">{value}</div>
    </Box>
  );
}

export default function App() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [trip, setTrip] = useState<TripPlan | null>(null);
  const [logTab, setLogTab] = useState(0);

  const handlePlan = async (payload: PlanTripRequest) => {
    setLoading(true);
    setError(null);
    try {
      const result = await planTrip(payload);
      setTrip(result);
      setLogTab(0);
      requestAnimationFrame(() => {
        document.getElementById("results")?.scrollIntoView({ behavior: "smooth", block: "start" });
      });
    } catch (err: unknown) {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        (err as Error).message ||
        "Failed to plan trip";
      setError(String(detail));
    } finally {
      setLoading(false);
    }
  };

  const summary = trip?.summary || {};
  const stepLabels = useMemo(() => {
    if (!trip) return [];
    return trip.stops
      .filter((s) => ["origin", "pickup", "fuel", "dropoff"].includes(s.type))
      .map((s, i) => ({
        id: `${s.type}-${i}-${s.arrive_at}`,
        label: s.label.replace(/^[^—]*—\s*/, "").slice(0, 28) || s.type,
      }))
      .slice(0, 8);
  }, [trip]);

  const gridRows =
    trip?.daily_logs.map((d, i) => ({
      id: i,
      date: d.date,
      driving: d.totals.driving,
      on_duty: d.totals.on_duty,
      sleeper: d.totals.sleeper,
      miles: d.total_miles_driving,
      available: d.recap.b_70_available_tomorrow ?? d.recap.b_available_tomorrow,
    })) || [];

  const columns: GridColDef[] = [
    { field: "date", headerName: "Date", flex: 1, minWidth: 110 },
    { field: "driving", headerName: "Drive (h)", width: 100 },
    { field: "on_duty", headerName: "On-duty ND", width: 120 },
    { field: "sleeper", headerName: "Sleeper", width: 100 },
    { field: "miles", headerName: "Miles", width: 90 },
    { field: "available", headerName: "Avail tomorrow", width: 130 },
  ];

  return (
    <LocalizationProvider dateAdapter={AdapterDayjs}>
      <Box className="routelog-shell">
        <AppBar
          position="sticky"
          elevation={0}
          sx={{
            bgcolor: "rgba(255,255,255,0.88)",
            backdropFilter: "blur(10px)",
            borderBottom: "2px solid",
            borderColor: "secondary.main",
            color: "secondary.main",
          }}
        >
          <Toolbar sx={{ gap: 2 }}>
            <Typography className="routelog-brand" sx={{ fontSize: 22 }}>
              RouteLog
            </Typography>
            <Typography
              sx={{
                color: "text.secondary",
                fontSize: 13,
                fontWeight: 600,
                display: { xs: "none", sm: "block" },
              }}
            >
              HOS · 70h / 8-day · property-carrying
            </Typography>
          </Toolbar>
        </AppBar>

        <Box className="routelog-hero">
          <Container maxWidth="lg" sx={{ py: { xs: 4, md: 6 } }}>
            <Box
              sx={{
                display: "grid",
                gap: { xs: 3, md: 5 },
                gridTemplateColumns: { xs: "1fr", md: "5fr 7fr" },
                alignItems: "stretch",
              }}
            >
              <Box>
                <Typography variant="overline" sx={{ color: "primary.main", display: "block", mb: 1.5 }}>
                  Spotter assessment
                </Typography>
                <Typography className="routelog-brand" sx={{ fontSize: { xs: "3.4rem", md: "5.2rem" }, mb: 2 }}>
                  RouteLog
                </Typography>
                <Typography sx={{ color: "text.secondary", maxWidth: 360, fontSize: 17, lineHeight: 1.45 }}>
                  Plan a compliant haul. Real road routing, rest & fuel stops, drawn daily logs.
                </Typography>
              </Box>
              <Paper
                elevation={0}
                sx={{
                  p: { xs: 2.5, md: 3.5 },
                  border: "2px solid",
                  borderColor: "secondary.main",
                }}
              >
                <TripPlanForm loading={loading} error={error} onSubmit={handlePlan} />
              </Paper>
            </Box>
          </Container>
        </Box>

        {trip && (
          <Box id="results" component="section">
            <Container maxWidth="lg" sx={{ py: 3 }}>
              <Box
                sx={{
                  display: "grid",
                  gridTemplateColumns: {
                    xs: "repeat(2, 1fr)",
                    sm: "repeat(3, 1fr)",
                    md: "repeat(6, 1fr)",
                  },
                  gap: 3,
                }}
              >
                <Metric label="Miles" value={String(summary.total_miles ?? "—")} />
                <Metric label="Drive hours" value={`${summary.total_driving_hours ?? "—"}`} />
                <Metric label="Log days" value={String(summary.days ?? "—")} />
                <Metric label="Cycle left" value={`${summary.cycle_remaining_at_end ?? "—"}h`} />
                <Metric label="Fuel stops" value={String(summary.fuel_stops ?? 0)} />
                <Metric label="Routing" value={String((summary.routing_provider as string) || (trip.approximate_routing ? "Approx" : "OSRM")).toUpperCase()} />
              </Box>

              {trip.adverse_conditions && (
                <Alert severity="warning" sx={{ mt: 2 }}>
                  Adverse conditions enabled — 11h/14h extended by +2h.
                </Alert>
              )}
            </Container>

            <Box className="routelog-map-bleed" sx={{ height: { xs: 420, md: 560 } }}>
              <RouteMap trip={trip} />
            </Box>

            <Container maxWidth="lg" sx={{ py: 4 }}>
              <Stack spacing={3.5}>
                {stepLabels.length > 0 && (
                  <Box>
                    <Typography variant="overline" sx={{ color: "text.secondary" }}>
                      Trip progress
                    </Typography>
                    <Paper
                      elevation={0}
                      sx={{ mt: 1, p: 2, overflowX: "auto", border: "1px solid", borderColor: "divider" }}
                    >
                      <Stepper
                        alternativeLabel
                        activeStep={stepLabels.length - 1}
                        sx={{ minWidth: 560 }}
                      >
                        {stepLabels.map((step) => (
                          <Step key={step.id} completed>
                            <StepLabel>{step.label}</StepLabel>
                          </Step>
                        ))}
                      </Stepper>
                    </Paper>
                  </Box>
                )}

                <Box>
                  <Typography variant="overline" sx={{ color: "text.secondary" }}>
                    Day summary
                  </Typography>
                  <Paper
                    elevation={0}
                    sx={{ mt: 1, height: 260, border: "1px solid", borderColor: "divider" }}
                  >
                    <DataGrid
                      rows={gridRows}
                      columns={columns}
                      disableRowSelectionOnClick
                      density="compact"
                      sx={{
                        border: 0,
                        "& .MuiDataGrid-columnHeaders": {
                          backgroundColor: "#F3F6F8",
                          fontFamily: "Syne, sans-serif",
                        },
                      }}
                    />
                  </Paper>
                </Box>

                {(summary.midnight_recaps as unknown[] | undefined)?.length ? (
                  <Alert severity="info">
                    Midnight recap: oldest day(s) rolled off the 8-day window during this plan.
                  </Alert>
                ) : null}

                <Box>
                  <Box
                    sx={{
                      display: "flex",
                      flexWrap: "wrap",
                      alignItems: "flex-start",
                      justifyContent: "space-between",
                      gap: 2,
                      mb: 2,
                    }}
                  >
                    <Box>
                      <Typography variant="h5" sx={{ mb: 0.5 }}>
                        Drivers Daily Logs
                      </Typography>
                      <Typography color="text.secondary" sx={{ maxWidth: 520 }}>
                        Drawn graph grid with remarks and 70/8 recap — one sheet per calendar day.
                      </Typography>
                    </Box>
                    <Button
                      variant="contained"
                      color="secondary"
                      startIcon={<DownloadIcon />}
                      href={tripPdfUrl(trip.id)}
                      target="_blank"
                      rel="noopener"
                      disabled={trip.pdf_status === "failed"}
                    >
                      {trip.pdf_status === "ready" || trip.pdf_url
                        ? "Download PDF report"
                        : "Generate / download PDF"}
                    </Button>
                  </Box>
                  <Tabs
                    value={logTab}
                    onChange={(_, v) => setLogTab(v)}
                    variant="scrollable"
                    scrollButtons="auto"
                    sx={{
                      mb: 2,
                      borderBottom: "2px solid",
                      borderColor: "secondary.main",
                      "& .MuiTab-root": { fontFamily: "Syne, sans-serif", fontWeight: 700 },
                    }}
                  >
                    {trip.daily_logs.map((d) => (
                      <Tab key={d.date} label={d.date} />
                    ))}
                  </Tabs>
                  {trip.daily_logs[logTab] && (
                    <DailyLogSheet log={trip.daily_logs[logTab]} tz={trip.home_terminal_tz} />
                  )}
                </Box>
              </Stack>
            </Container>
          </Box>
        )}
      </Box>
    </LocalizationProvider>
  );
}
