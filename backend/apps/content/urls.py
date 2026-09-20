"""Content routes. Mounted under /api/v1/ by config.api_urls."""

from django.urls import path

from apps.content import views

urlpatterns = [
    path("gallery", views.GalleryView.as_view(), name="gallery"),
    path("testimonials", views.TestimonialListView.as_view(), name="testimonials"),
    path("faqs", views.FaqListView.as_view(), name="faqs"),
    path("legal/<slug:slug>", views.LegalPageView.as_view(), name="legal-page"),
]
