from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path


def root(_request):
    return JsonResponse(
        {
            "service": "RouteLog HOS API",
            "status": "ok",
            "app": "https://spotter-hos-web.vercel.app",
            "health": "/api/v1/health/",
            "plan": "POST /api/v1/trips/plan/",
        }
    )


urlpatterns = [
    path("", root, name="root"),
    path("admin/", admin.site.urls),
    path("api/v1/", include("apps.trips.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
