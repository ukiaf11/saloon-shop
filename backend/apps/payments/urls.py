from django.urls import path

from apps.payments import views

urlpatterns = [
    path("payments/options", views.PaymentOptionsView.as_view(), name="payment-options"),
    path("payments/qr-image", views.qr_image, name="payment-qr-image"),
    path(
        "orders/<uuid:order_id>/upi-payment",
        views.UpiClaimView.as_view(),
        name="order-upi-payment",
    ),
    path(
        "owner/payment-settings",
        views.OwnerPaymentSettingsView.as_view(),
        name="owner-payment-settings",
    ),
    path("owner/payments", views.OwnerPaymentsView.as_view(), name="owner-payments"),
    path(
        "owner/payments/<uuid:payment_id>/confirm",
        views.OwnerConfirmPaymentView.as_view(),
        name="owner-payment-confirm",
    ),
    path(
        "owner/payments/<uuid:payment_id>/reject",
        views.OwnerRejectPaymentView.as_view(),
        name="owner-payment-reject",
    ),
]
