import uuid

from django.db import models

from apps.drivers.models import Driver
from apps.trips.models import Trip


class LogEntry(models.Model):
    """Granular duty-status changes — indexed for rolling 8-day queries."""

    class Status(models.TextChoices):
        OFF = "OFF", "Off Duty"
        SB = "SB", "Sleeper Berth"
        D = "D", "Driving"
        ON = "ON", "On Duty (not driving)"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    trip = models.ForeignKey(Trip, on_delete=models.CASCADE, related_name="log_entries")
    driver = models.ForeignKey(Driver, on_delete=models.CASCADE, related_name="log_entries")
    status = models.CharField(max_length=3, choices=Status.choices)
    start_at = models.DateTimeField()
    end_at = models.DateTimeField()
    duration_minutes = models.PositiveIntegerField(default=0)
    location_label = models.CharField(max_length=255, blank=True)
    lat = models.FloatField(null=True, blank=True)
    lng = models.FloatField(null=True, blank=True)
    remark = models.TextField(blank=True)
    is_34h_restart_segment = models.BooleanField(default=False)

    class Meta:
        ordering = ["start_at"]
        indexes = [
            models.Index(fields=["driver", "start_at"], name="log_driver_start_idx"),
            models.Index(fields=["driver", "end_at"], name="log_driver_end_idx"),
            models.Index(fields=["trip", "start_at"], name="log_trip_start_idx"),
            models.Index(
                fields=["driver", "status", "start_at"],
                name="log_driver_status_start_idx",
            ),
        ]


class DailyLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    trip = models.ForeignKey(Trip, on_delete=models.CASCADE, related_name="daily_logs")
    log_date = models.DateField()
    from_location = models.CharField(max_length=255, blank=True)
    to_location = models.CharField(max_length=255, blank=True)
    total_miles_driving = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    grid_segments = models.JSONField(default=list)
    totals = models.JSONField(default=dict)
    remarks = models.JSONField(default=list)
    recap = models.JSONField(default=dict)

    class Meta:
        ordering = ["log_date"]
        unique_together = [("trip", "log_date")]
