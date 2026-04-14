from django.urls import path

from .views import DoctorsAvailabilityView, QueueListView

urlpatterns = [
    path("queue/", QueueListView.as_view(), name="queue-list"),
    path("doctors/availability/", DoctorsAvailabilityView.as_view(), name="doctors-availability"),
]
