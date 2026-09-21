from django.urls import path

from apps.promotions.views import PromotionTodayView

urlpatterns = [
    path("promotion/today", PromotionTodayView.as_view(), name="promotion-today"),
]
