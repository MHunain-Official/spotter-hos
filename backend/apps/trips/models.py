import uuid

from django.db import models

from apps.drivers.models import Driver


class Trip(models.Model):
    class Status(models.TextChoices):
        PLANNING = "planning", "Planning"
        READY = "ready", "Ready"
        FAILED = "failed", "Failed"

    class PdfStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        READY = "ready", "Ready"
        FAILED = "failed", "Failed"
        SKIPPED = "skipped", "Skipped"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    driver = models.ForeignKey(Driver, on_delete=models.CASCADE, related_name="trips")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PLANNING)

    current_address = models.CharField(max_length=255)
    pickup_address = models.CharField(max_length=255)
    dropoff_address = models.CharField(max_length=255)
    current_lat = models.FloatField(null=True, blank=True)
    current_lng = models.FloatField(null=True, blank=True)
    pickup_lat = models.FloatField(null=True, blank=True)
    pickup_lng = models.FloatField(null=True, blank=True)
    dropoff_lat = models.FloatField(null=True, blank=True)
    dropoff_lng = models.FloatField(null=True, blank=True)

    current_cycle_used_hours = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    adverse_conditions = models.BooleanField(default=False)
    auto_34h_restart = models.BooleanField(default=True)
    trip_start_at = models.DateTimeField()
    home_terminal_tz = models.CharField(max_length=64, default="America/Chicago")

    route_geometry = models.JSONField(default=list, blank=True)
    summary = models.JSONField(default=dict, blank=True)
    approximate_routing = models.BooleanField(default=False)

    pdf_status = models.CharField(
        max_length=16, choices=PdfStatus.choices, default=PdfStatus.SKIPPED
    )
    pdf_file = models.FileField(upload_to="trip_pdfs/", null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["created_at"]),
            models.Index(fields=["driver", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"Trip {self.id} ({self.status})"


class TripStop(models.Model):
    class StopType(models.TextChoices):
        ORIGIN = "origin", "Origin"
        PICKUP = "pickup", "Pickup"
        FUEL = "fuel", "Fuel"
        REST = "rest", "Rest"
        DROPOFF = "dropoff", "Dropoff"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    trip = models.ForeignKey(Trip, on_delete=models.CASCADE, related_name="stops")
    stop_type = models.CharField(max_length=16, choices=StopType.choices)
    label = models.CharField(max_length=255)
    lat = models.FloatField()
    lng = models.FloatField()
    arrive_at = models.DateTimeField()
    depart_at = models.DateTimeField()
    sequence = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sequence", "arrive_at"]
        indexes = [
            models.Index(fields=["trip", "sequence"]),
        ]
