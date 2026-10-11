"""Relire, corriger et supprimer une revue depuis l'appli (règles dans services/editing.py).

- PATCH  /jobs/<id>/                      renommer
- DELETE /jobs/<id>/                      supprimer (revue terminée ou en échec)
- PATCH  /jobs/<id>/review/               corriger notices, ordre, rubriques, titre, date
- POST   /jobs/<id>/review/restore/       revenir à la version rédigée par l'IA
- PATCH  /jobs/<id>/highlights/<hid>/     masquer / réafficher un point clé, changer sa catégorie
"""
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.exceptions import APIException, NotFound, PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import IsOrgAdmin, IsOrgMember, OrganizationContextMixin

from .models import Highlight, PressReviewJob
from .serializers import GeneratedReviewSerializer, HighlightSerializer, PressReviewJobDetailSerializer
from .serializers_editing import HighlightUpdateSerializer, JobUpdateSerializer, ReviewUpdateSerializer
from .services import editing
from .views import JobDetailView, JobReviewView

DELETE_FORBIDDEN_MESSAGE = (
    "Seul l'auteur de la revue, le propriétaire ou un administrateur de l'organisation peut la supprimer."
)


class ReviewConflict(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = editing.CONFLICT_MESSAGE
    default_code = "conflict"


def _visible_job(request, pk):
    return get_object_or_404(PressReviewJob.objects.visible(), pk=pk, organization=request.organization)


def _review_of(job):
    review = getattr(job, "review", None)
    if review is None:
        raise NotFound("La revue n'est pas encore disponible pour ce job.")
    return review


class JobDetailEditView(JobDetailView):
    """GET : détail · PATCH : renommer · DELETE : supprimer."""

    def patch(self, request, *args, **kwargs):
        job = self.get_object()
        serializer = JobUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            editing.rename_job(job, serializer.validated_data["title"])
        except editing.ReviewEditError as exc:
            raise ValidationError(str(exc)) from exc
        return Response(PressReviewJobDetailSerializer(job).data)

    def delete(self, request, *args, **kwargs):
        job = self.get_object()
        is_org_admin = IsOrgAdmin().has_permission(request, self)
        if not editing.can_delete_job(job, request.user, is_org_admin=is_org_admin):
            raise PermissionDenied(DELETE_FORBIDDEN_MESSAGE)
        try:
            editing.delete_press_review_job(job)
        except editing.ReviewEditError as exc:
            raise ValidationError(str(exc)) from exc
        return Response(status=status.HTTP_204_NO_CONTENT)


class JobReviewEditView(JobReviewView):
    """GET : la revue · PATCH : la corriger (tout membre de l'organisation)."""

    def patch(self, request, pk):
        review = _review_of(_visible_job(request, pk))
        serializer = ReviewUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        changes = dict(serializer.validated_data)
        options = {}
        if "expected_edited_at" in changes:
            options["expected_edited_at"] = changes.pop("expected_edited_at")
        try:
            review = editing.update_review(review, user=request.user, changes=changes, **options)
        except editing.ReviewEditError as exc:
            raise ValidationError(str(exc)) from exc
        except editing.ReviewEditConflict as exc:
            raise ReviewConflict(str(exc)) from exc
        return Response(GeneratedReviewSerializer(review).data)


class JobReviewRestoreView(OrganizationContextMixin, APIView):
    permission_classes = [IsAuthenticated, IsOrgMember]

    def post(self, request, pk):
        review = _review_of(_visible_job(request, pk))
        try:
            review = editing.restore_original_review(review)
        except editing.ReviewEditError as exc:
            raise ValidationError(str(exc)) from exc
        return Response(GeneratedReviewSerializer(review).data)


class JobHighlightDetailView(OrganizationContextMixin, APIView):
    permission_classes = [IsAuthenticated, IsOrgMember]

    def patch(self, request, pk, highlight_pk):
        job = _visible_job(request, pk)
        highlight = get_object_or_404(Highlight.objects.select_related("category", "job"), pk=highlight_pk, job=job)
        serializer = HighlightUpdateSerializer(data=request.data, organization=request.organization)
        serializer.is_valid(raise_exception=True)
        highlight = editing.update_highlight(highlight, changes=serializer.validated_data)
        return Response(HighlightSerializer(highlight).data)
