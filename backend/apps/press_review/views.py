from django.db.models import ProtectedError, Q
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
)
from .services.jobs import create_press_review_job


def _start_pipeline(job):
    # Import tardif : évite un import circulaire au démarrage (ai_pipeline importe
    # des modèles de press_review) et permet à ce module de charger même si
    # ai_pipeline n'est pas encore construit.
    from apps.ai_pipeline.tasks import run_press_review_pipeline

    run_press_review_pipeline(str(job.id))


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
            original_filename=f.name,
        )
        return Response(SourceDocumentSerializer(document).data, status=status.HTTP_201_CREATED)


class JobListCreateView(OrganizationContextMixin, generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated, IsOrgMember]
    pagination_class = StandardPagination
    serializer_class = PressReviewJobListSerializer

    def get_queryset(self):
        qs = PressReviewJob.objects.filter(organization=self.request.organization)
        status_param = self.request.query_params.get("status")
        if status_param:
            qs = qs.filter(status=status_param)
        return qs

    def create(self, request, *args, **kwargs):
        from apps.billing.services import SubscriptionService

        if not SubscriptionService.has_quota_for_new_review(organization=request.organization):
            raise PermissionDenied(
                "Aucun abonnement actif ou quota de revues atteint pour cette période. "
                "Vérifiez votre abonnement dans les paramètres de facturation."
            )

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


class JobDetailView(OrganizationContextMixin, generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated, IsOrgMember]
    serializer_class = PressReviewJobDetailSerializer

    def get_queryset(self):
        return PressReviewJob.objects.filter(organization=self.request.organization)


class JobHighlightsView(OrganizationContextMixin, generics.ListAPIView):
    permission_classes = [IsAuthenticated, IsOrgMember]
    serializer_class = HighlightSerializer
    pagination_class = None

    def get_queryset(self):
        job = get_object_or_404(PressReviewJob, pk=self.kwargs["pk"], organization=self.request.organization)
        qs = Highlight.objects.filter(job=job).select_related("category")
        category_type = self.request.query_params.get("category")
        if category_type:
            qs = qs.filter(category__type=category_type)
        return qs


class JobReviewView(OrganizationContextMixin, APIView):
    permission_classes = [IsAuthenticated, IsOrgMember]

    def get(self, request, pk):
        job = get_object_or_404(PressReviewJob, pk=pk, organization=request.organization)
        review = getattr(job, "review", None)
        if review is None:
            raise NotFound("La revue n'est pas encore disponible pour ce job.")
        return Response(GeneratedReviewSerializer(review).data)


class JobReviewExportView(OrganizationContextMixin, APIView):
    permission_classes = [IsAuthenticated, IsOrgMember]

    def get(self, request, pk):
        job = get_object_or_404(PressReviewJob, pk=pk, organization=request.organization)
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
            PressReviewJob, pk=pk, organization=request.organization, status=PressReviewJob.Status.FAILED
        )
        # Ne PAS transitionner ici : task_extract_text le fait déjà elle-même
        # (FAILED -> TEXT_EXTRACTION est explicitement autorisé). Le faire aussi ici
        # ferait échouer la tâche sur un double FAILED/TEXT_EXTRACTION -> TEXT_EXTRACTION.
        _start_pipeline(job)
        job.refresh_from_db()  # cf. commentaire équivalent dans JobListCreateView.create
        return Response(PressReviewJobDetailSerializer(job).data)
