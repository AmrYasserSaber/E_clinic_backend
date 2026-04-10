from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import AdminUserViewSet, PatientViewSet

router = DefaultRouter()
router.register(r"users", AdminUserViewSet, basename="admin-users")
router.register(r"patients", PatientViewSet, basename="patients")

urlpatterns = [
    path("", include(router.urls)),
]