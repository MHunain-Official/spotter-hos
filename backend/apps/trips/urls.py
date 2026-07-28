from django.urls import path

from apps.trips.views import HealthView, PlanTripView, TripDetailView, TripPdfView

urlpatterns = [
    path("health/", HealthView.as_view(), name="health"),
    path("trips/plan/", PlanTripView.as_view(), name="trips-plan"),
    path("trips/<uuid:trip_id>/", TripDetailView.as_view(), name="trips-detail"),
    path("trips/<uuid:trip_id>/pdf/", TripPdfView.as_view(), name="trips-pdf"),
]
