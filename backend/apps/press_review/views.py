import logging

from django.db.models import Count, ProtectedError, Q
from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.pagination import StandardPagination
from apps.core.permissions import IsOrgAdmin, IsOrgMember, OrganizationContextMixin

from .models import DetectionCategory, Highlight, PressReviewJob, SourceDocument
from .serializers import (
    DetectionCategorySerializer,
    GeneratedReviewSerializer,
    HighlightSerializer,
    JobCreateSerializer,
    PressReviewJobDetailSerializer,
    PressReviewJobListSerializer,
    SourceDocumentSerializer,
    SourceDocumentUploadSerializer,
    classify_upload_kind,
)
from .services.jobs import create_press_review_job
from .services.pipeline import InvalidTransition, mark_dispatch_failed, transition_job

logger = logging.getLogger(__name__)

DISPATCH_FAILED_MESSAGE = (
    "Impossible de démarrer l'analyse en arrière-plan (file de tâches indisponible). "
    "Réessayez dans un instant."
)


def _start_pipeline(job):
    """Met le pipeline en file d'attente et rend la main immédiatement : l'analyse tourne
    ensuite dans un worker Celery, l'interface suit sa progression par polling."""
    # Import tardif : évite un import circulaire au démarrage (ai_pipeline importe
    # des modèles de press_review).
    from apps.ai_pipeline.tasks import run_press_review_pipeline

    job.refresh_from_db(fields=["updated_at"])
    updated_before = job.updated_at
    try:
        run_press_review_pipeline(str(job.id))
    except Exception:
        logger.exception("Le lancement du pipeline a levé une erreur pour le job %s", job.id)
        # Deux origines possibles, à distinguer :
        # - mode eager (dev) : une tâche a tourné puis échoué ; elle a déjà mis le job en
        #   FAILED avec un message précis (updated_at a changé) -> on ne touche à rien ;
        # - mise en file impossible (broker injoignable) : aucune tâche n'a tourné
        #   (updated_at inchangé) -> sans ceci le job resterait bloqué à UPLOADED sans
        #   aucune erreur visible.
        job.refresh_from_db(fields=["updated_at"])
        if job.updated_at == updated_before:
            mark_dispatch_failed(job, DISPATCH_FAILED_MESSAGE)


class DetectionCategoryListCreateView(OrganizationContextMixin, generics.ListCreateAPIView):
    serializer_class = DetectionCategorySerializer

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAuthenticated(), IsOrgAdmin()]
        return [IsAuthenticated(), IsOrgMember()]

    def get_queryset(self):
        return DetectionCategory.objects.filter(
            Q(organization=self.request.organization) | Q(organization__isnull=True)
        ).order_by("sort_order", "name")

    def perform_create(self, serializer):
        serializer.save(organization=self.request.organization)


class DetectionCategoryDetailView(OrganizationContextMixin, generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated, IsOrgAdmin]
    serializer_class = DetectionCategorySerializer

    def get_queryset(self):
        # Seules les catégories propres à l'organisation sont modifiables ici (les
        # catégories globales, organization=None, sont gérées via l'admin Django).
        return DetectionCategory.objects.filter(organization=self.request.organization)

    def perform_destroy(self, instance):
        try:
            instance.delete()
        except ProtectedError as exc:
            raise ValidationError(
                "Cette catégorie est utilisée par des points saillants déjà détectés et ne peut pas être "
                "supprimée — désactivez-la plutôt (is_active=false)."
            ) from exc


class SourceDocumentListCreateView(OrganizationContextMixin, generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated, IsOrgMember]
    serializer_class = SourceDocumentSerializer
    pagination_class = StandardPagination

    def get_queryset(self):
        return SourceDocument.objects.filter(
            organization=self.request.organization, job__isnull=True
        ).order_by("-created_at")

    def create(self, request, *args, **kwargs):
        upload_serializer = SourceDocumentUploadSerializer(data=request.data)
        upload_serializer.is_valid(raise_exception=True)
        f = upload_serializer.validated_data["file"]
        document = SourceDocument.objects.create(
            organization=request.organization,
            uploaded_by=request.user,
            file=f,
            original_filename=f.original_name,
            kind=classify_upload_kind(f),
        )
        return Response(
            SourceDocumentSerializer(document, context=self.get_serializer_context()).data,
            status=status.HTTP_201_CREATED,
        )


class SourceDocumentDetailView(OrganizationContextMixin, generics.DestroyAPIView):
    """Retire un document téléversé par erreur, tant qu'il n'a pas été rattaché à une revue
    (un document déjà analysé fait partie de l'historique de sa revue : on n'y touche pas)."""

    permission_classes = [IsAuthenticated, IsOrgMember]

    def get_queryset(self):
        return SourceDocument.objects.filter(organization=self.request.organization, job__isnull=True)

    def perform_destroy(self, instance):
        instance.file.delete(save=False)
        instance.delete()


class JobListCreateView(OrganizationContextMixin, generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated, IsOrgMember]
    pagination_class = StandardPagination
    serializer_class = PressReviewJobListSerializer

    def get_queryset(self):
        # order_by explicite : Django n'applique pas Meta.ordering aux requêtes GROUP BY
        # (annotate + Count), la pagination serait alors instable.
        qs = (
            PressReviewJob.objects.visible()
            .filter(organization=self.request.organization)
            .annotate(
                documents_count=Count("documents", distinct=True),
                # Les points clés masqués par l'utilisateur (faux positifs) ne comptent pas.
                highlights_count=Count("highlights", filter=Q(highlights__hidden=False), distinct=True),
            )
            .order_by("-created_at")
        )
        status_param = self.request.query_params.get("status")
        if status_param:
            qs = qs.filter(status=status_param)
        return qs

    def create(self, request, *args, **kwargs):
        from apps.billing.services import SubscriptionService

        denial = SubscriptionService.review_quota_denial(organization=request.organization)
        if denial:
            raise PermissionDenied(denial)

        serializer = JobCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            job, _documents = create_press_review_job(
                organization=request.organization,
                created_by=request.user,
                document_ids=[str(i) for i in serializer.validated_data["document_ids"]],
                title=serializer.validated_data.get("title", ""),
            )
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc

        _start_pipeline(job)
        # En mode CELERY_TASK_ALWAYS_EAGER (dev/tests), le pipeline s'exécute
        # synchroniquement ci-dessus sur des instances de `job` rechargées depuis la
        # DB par chaque tâche : notre propre instance `job` est restée périmée (encore
        # UPLOADED). En mode async normal, ce refresh est un no-op inoffensif (rien n'a
        # encore pu s'exécuter).
        job.refresh_from_db()
        return Response(PressReviewJobDetailSerializer(job).data, status=status.HTTP_201_CREATED)


ACTIVE_JOB_STATUSES = (
    PressReviewJob.Status.UPLOADED,
    PressReviewJob.Status.TEXT_EXTRACTION,
    PressReviewJob.Status.CHUNKING_SUMMARIZATION,
    PressReviewJob.Status.HIGHLIGHT_DETECTION,
    PressReviewJob.Status.REVIEW_DRAFTING,
)


class JobStatsView(OrganizationContextMixin, APIView):
    """Chiffres du tableau de bord, calculés sur TOUTES les revues de l'organisation (la
    liste des revues est paginée : la compter côté navigateur sous-estimerait)."""

    permission_classes = [IsAuthenticated, IsOrgMember]

    def get(self, request):
        stats = PressReviewJob.objects.visible().filter(organization=request.organization).aggregate(
            total=Count("id"),
            active=Count("id", filter=Q(status__in=ACTIVE_JOB_STATUSES)),
            ready=Count(
                "id", filter=Q(status__in=[PressReviewJob.Status.REVIEW_READY, PressReviewJob.Status.EXPORTED])
            ),
            failed=Count("id", filter=Q(status=PressReviewJob.Status.FAILED)),
        )
        stats["highlights"] = Highlight.objects.filter(job__organization=request.organization, hidden=False).count()
        stats["documents"] = SourceDocument.objects.filter(
            organization=request.organization, job__isnull=False
        ).count()
        return Response(stats)


class JobDetailView(OrganizationContextMixin, generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated, IsOrgMember]
    serializer_class = PressReviewJobDetailSerializer

    def get_queryset(self):
        return PressReviewJob.objects.visible().filter(organization=self.request.organization)


class JobHighlightsView(OrganizationContextMixin, generics.ListAPIView):
    permission_classes = [IsAuthenticated, IsOrgMember]
    serializer_class = HighlightSerializer
    pagination_class = None

    def get_queryset(self):
        job = get_object_or_404(
            PressReviewJob.objects.visible(), pk=self.kwargs["pk"], organization=self.request.organization
        )
        qs = Highlight.objects.filter(job=job).select_related("category")
        category_type = self.request.query_params.get("category")
        if category_type:
            qs = qs.filter(category__type=category_type)
        hidden = self.request.query_params.get("hidden")  # ?hidden=false : sans les points masqués
        if hidden in ("true", "false"):
            qs = qs.filter(hidden=hidden == "true")
        return qs


class JobReviewView(OrganizationContextMixin, APIView):
    permission_classes = [IsAuthenticated, IsOrgMember]

    def get(self, request, pk):
        job = get_object_or_404(PressReviewJob.objects.visible(), pk=pk, organization=request.organization)
        review = getattr(job, "review", None)
        if review is None:
            raise NotFound("La revue n'est pas encore disponible pour ce job.")
        return Response(GeneratedReviewSerializer(review).data)


class JobReviewExportView(OrganizationContextMixin, APIView):
    permission_classes = [IsAuthenticated, IsOrgMember]

    def get(self, request, pk):
        job = get_object_or_404(PressReviewJob.objects.visible(), pk=pk, organization=request.organization)
        review = getattr(job, "review", None)
        if review is None:
            raise NotFound("La revue n'est pas encore disponible pour ce job.")

        # NB: le paramètre s'appelle `export_format`, pas `format` — DRF réserve `format`
        # pour sa propre négociation de contenu (choix du renderer) et répond 404 si
        # aucun renderer enregistré ne porte ce nom (on n'a que du JSON).
        fmt = request.query_params.get("export_format", "pdf")
        if fmt not in ("pdf", "docx"):
            raise ValidationError("export_format doit être 'pdf' ou 'docx'.")

        from apps.ai_pipeline.export import get_or_render_export

        file_field = get_or_render_export(review, fmt=fmt)
        return Response({"url": request.build_absolute_uri(file_field.url)})


class JobRetryView(OrganizationContextMixin, APIView):
    permission_classes = [IsAuthenticated, IsOrgMember]

    def post(self, request, pk):
        job = get_object_or_404(
            PressReviewJob.objects.visible(),
            pk=pk,
            organization=request.organization,
            status=PressReviewJob.Status.FAILED,
        )
        # On repasse tout de suite le job en TEXT_EXTRACTION : en arrière-plan, le worker
        # peut mettre plusieurs secondes à prendre la tâche, et un job resté FAILED
        # arrêterait le polling du frontend (qui ne suit que les statuts « actifs »).
        # C'est sûr car task_extract_text est idempotent (enter_step ne re-transitionne
        # pas un job déjà dans l'étape).
        try:
            transition_job(job, PressReviewJob.Status.TEXT_EXTRACTION)
        except InvalidTransition as exc:
            raise ValidationError(str(exc)) from exc
        _start_pipeline(job)
        job.refresh_from_db()  # cf. commentaire équivalent dans JobListCreateView.create
        return Response(PressReviewJobDetailSerializer(job).data)
