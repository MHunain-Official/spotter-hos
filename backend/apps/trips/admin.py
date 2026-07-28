from django.contrib import admin

from apps.drivers.models import Driver
from apps.logs.models import DailyLog, LogEntry
from apps.trips.models import Trip, TripStop

admin.site.register(Driver)
admin.site.register(Trip)
admin.site.register(TripStop)
admin.site.register(LogEntry)
admin.site.register(DailyLog)
