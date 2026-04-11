from django.urls import include, path

urlpatterns = [
    path("auth/", include("users.urls")),
    path("", include("schedules.urls")),
    path("", include("analytics.urls")),
    path("", include("adminpanel.urls")),
    path("", include("reports.urls")),
]
