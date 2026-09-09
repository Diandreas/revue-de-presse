from django.urls import path

from .views import (
    DetectionCategoryDetailView,
    DetectionCategoryListCreateView,
    JobDetailView,
    JobHighlightsView,
    JobListCreateView,
    JobRetryView,
    JobReviewExportView,
    JobReviewView,
    SourceDocumentListCreateView,
)

urlpatterns = [
    path("documents/", SourceDocumentListCreateView.as_view(), name="document-list-create"),
    path("jobs/", JobListCreateView.as_view(), name="job-list-create"),
    path("jobs/<uuid:pk>/", JobDetailView.as_view(), name="job-detail"),
    path("jobs/<uuid:pk>/highlights/", JobHighlightsView.as_view(), name="job-highlights"),
    path("jobs/<uuid:pk>/review/", JobReviewView.as_view(), name="job-review"),
    path("jobs/<uuid:pk>/review/export/", JobReviewExportView.as_view(), name="job-review-export"),
    path("jobs/<uuid:pk>/retry/", JobRetryView.as_view(), name="job-retry"),
    path("detection-categories/", DetectionCategoryListCreateView.as_view(), name="detection-category-list-create"),
    path("detection-categories/<uuid:pk>/", DetectionCategoryDetailView.as_view(), name="detection-category-detail"),
]
