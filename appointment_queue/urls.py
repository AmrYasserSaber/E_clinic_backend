from django.urls import path

from .views import QueueListView

urlpatterns = [
    path("queue/", QueueListView.as_view(), name="queue-list"),
]
