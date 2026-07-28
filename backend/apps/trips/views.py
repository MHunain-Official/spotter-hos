from django.db import connection
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.logs.pdf import build_trip_pdf_bytes, generate_and_store_trip_pdf
from apps.trips.models import Trip
from apps.trips.serializers import PlanTripSerializer
from apps.trips.services import PlanTripError, plan_trip, serialize_trip


class HealthView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        db_ok = False
        try:
            connection.ensure_connection()
            db_ok = True
        except Exception as exc:  # noqa: BLE001
            return JsonResponse(
                {"status": "degraded", "database": False, "error": str(exc)},
                status=503,
            )
        return Response({"status": "ok", "database": db_ok})


class PlanTripView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        ser = PlanTripSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            payload = plan_trip(ser.validated_data)
        except PlanTripError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(payload, status=status.HTTP_201_CREATED)


class TripDetailView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request, trip_id):
        try:
            trip = Trip.objects.prefetch_related("stops", "daily_logs").get(pk=trip_id)
        except Trip.DoesNotExist:
            return Response({"detail": "Not found"}, status=status.HTTP_404_NOT_FOUND)
        return Response(serialize_trip(trip))


class TripPdfView(APIView):
    """Download Drivers Daily Log PDF (regenerates on demand — safe for serverless)."""

    authentication_classes = []
    permission_classes = []

    def get(self, request, trip_id):
        try:
            trip = Trip.objects.prefetch_related("daily_logs").get(pk=trip_id)
        except Trip.DoesNotExist as exc:
            raise Http404("Trip not found") from exc

        # Prefer stored file when present; otherwise build in-memory (Vercel /tmp is ephemeral)
        try:
            if (
                trip.pdf_file
                and trip.pdf_status == Trip.PdfStatus.READY
                and trip.pdf_file.storage.exists(trip.pdf_file.name)
            ):
                return FileResponse(
                    trip.pdf_file.open("rb"),
                    as_attachment=True,
                    filename=f"routelog-trip-{trip.id}.pdf",
                    content_type="application/pdf",
                )
        except Exception:  # noqa: BLE001
            pass

        try:
            pdf_bytes = build_trip_pdf_bytes(trip)
            try:
                generate_and_store_trip_pdf(trip)
            except Exception:  # noqa: BLE001
                pass
        except Exception as exc:  # noqa: BLE001
            return Response(
                {"detail": f"PDF generation failed: {exc}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        response = HttpResponse(pdf_bytes, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="routelog-trip-{trip.id}.pdf"'
        return response
