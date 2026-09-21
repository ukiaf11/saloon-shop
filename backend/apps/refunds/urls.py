from django.urls import path

from apps.refunds import views

urlpatterns = [
    path("owner/refunds", views.OwnerRefundsView.as_view(), name="owner-refunds"),
    path(
        "owner/refunds/<uuid:refund_id>/mark-sent",
        views.OwnerMarkRefundSentView.as_view(),
        name="owner-refund-mark-sent",
    ),
]
