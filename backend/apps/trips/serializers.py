from rest_framework import serializers


class PlanTripSerializer(serializers.Serializer):
    current_location = serializers.CharField(max_length=255)
    pickup_location = serializers.CharField(max_length=255)
    dropoff_location = serializers.CharField(max_length=255)
    current_cycle_used_hours = serializers.FloatField(min_value=0, max_value=70, default=0)
    trip_start = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    adverse_conditions = serializers.BooleanField(required=False, default=False)
    auto_34h_restart = serializers.BooleanField(required=False, default=True)
    home_terminal_tz = serializers.CharField(required=False, default="America/Chicago")
