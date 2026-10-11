from django.urls import path

from .views import (
    DetectionCategoryDetailView,
    DetectionCategoryListCreateView,
    JobHighlightsView,
    JobListCreateView,
    JobRetryView,
    JobReviewExportView,
    JobStatsView,
    SourceDocumentDetailView,
    SourceDocumentListCreateView,
)
from .views_editing import JobDetailEditView, JobHighlightDetailView, JobReviewEditView, JobReviewRestoreView

urlpatterns = [
    path("documents/", SourceDocumentListCreateView.as_view(), name="document-list-create"),
    path("documents/<uuid:pk>/", SourceDocumentDetailView.as_view(), name="document-detail"),
    path("jobs/", JobListCreateView.as_view(), name="job-list-create"),
    path("jobs/stats/", JobStatsView.as_view(), name="job-stats"),
    path("jobs/<uuid:pk>/", JobDetailEditView.as_view(), name="job-detail"),
    path("jobs/<uuid:pk>/highlights/", JobHighlightsView.as_view(), name="job-highlights"),
    path(
        "jobs/<uuid:pk>/highlights/<uuid:highlight_pk>/", JobHighlightDetailView.as_view(), name="job-highlight-detail"
    ),
    path("jobs/<uuid:pk>/review/", JobReviewEditView.as_view(), name="job-review"),
    path("jobs/<uuid:pk>/review/restore/", JobReviewRestoreView.as_view(), name="job-review-restore"),
    path("jobs/<uuid:pk>/review/export/", JobReviewExportView.as_view(), name="job-review-export"),
    path("jobs/<uuid:pk>/retry/", JobRetryView.as_view(), name="job-retry"),
    path("detection-categories/", DetectionCategoryListCreateView.as_view(), name="detection-category-list-create"),
    path("detection-categories/<uuid:pk>/", DetectionCategoryDetailView.as_view(), name="detection-category-detail"),
]
