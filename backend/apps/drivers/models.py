import uuid

from django.db import models


class Driver(models.Model):
    class CycleType(models.TextChoices):
        SEVENTY_EIGHT = "70_8", "70-hour / 8-day"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    display_name = models.CharField(max_length=120, default="Demo Driver")
    home_terminal_tz = models.CharField(max_length=64, default="America/Chicago")
    cycle_type = models.CharField(
        max_length=8, choices=CycleType.choices, default=CycleType.SEVENTY_EIGHT
    )
    current_cycle_used_hours = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    last_34h_restart_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return self.display_name
