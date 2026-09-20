from django.urls import path

from apps.salons.views import SalonView

urlpatterns = [
    path("salon", SalonView.as_view(), name="salon"),
]
