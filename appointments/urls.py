from django.urls import path

from appointments.views import AvailableSlotsView

urlpatterns = [
    path("slots/", AvailableSlotsView.as_view(), name="available-slots"),
]
