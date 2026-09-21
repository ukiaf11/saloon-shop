from django.urls import path

from apps.orders import views

urlpatterns = [
    path("orders/quote", views.QuoteView.as_view(), name="order-quote"),
    path("orders", views.OrderCreateView.as_view(), name="order-create"),
    path("orders/<uuid:order_id>", views.OrderDetailView.as_view(), name="order-detail"),
]
