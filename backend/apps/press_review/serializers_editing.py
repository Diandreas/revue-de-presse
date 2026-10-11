"""Entrées des corrections de la revue (PATCH). La validation fine des notices — avec des
messages qui disent quelle notice corriger — est dans services/editing.py."""
from django.db.models import Q
from rest_framework import serializers

from .models import DetectionCategory
from .services.editing import MAX_TITLE_LENGTH

TITLE_ERRORS = {
    "blank": "Le titre de la revue ne peut pas être vide.",
    "max_length": f"Le titre ne doit pas dépasser {MAX_TITLE_LENGTH} caractères.",
    "invalid": "Le titre doit être du texte.",
    "null": "Le titre de la revue ne peut pas être vide.",
}


class JobUpdateSerializer(serializers.Serializer):
    """Renommer une revue (PATCH /jobs/<id>/)."""

    title = serializers.CharField(max_length=MAX_TITLE_LENGTH, error_messages=TITLE_ERRORS)


class ReviewUpdateSerializer(serializers.Serializer):
    """PATCH /jobs/<id>/review/ — tous les champs sont facultatifs, au moins un est requis.

    `sections` reprend la forme renvoyée par GET (rubriques `key` + notices `source`,
    `headline`, `summary`, `documents`) dans l'ordre voulu. `expected_edited_at` (facultatif)
    est la date de la dernière correction connue du client : si quelqu'un a corrigé la revue
    depuis, la requête est refusée (409) au lieu d'écraser son travail."""

    title = serializers.CharField(max_length=MAX_TITLE_LENGTH, required=False, error_messages=TITLE_ERRORS)
    date_label = serializers.CharField(required=False, allow_blank=True, trim_whitespace=False)
    country = serializers.CharField(required=False, allow_blank=True, trim_whitespace=False)
    sections = serializers.JSONField(required=False)
    expected_edited_at = serializers.DateTimeField(required=False, allow_null=True)

    def validate(self, attrs):
        if not {"title", "date_label", "country", "sections"} & set(attrs):
            raise serializers.ValidationError("Aucune modification à enregistrer.")
        return attrs


class HighlightUpdateSerializer(serializers.Serializer):
    """PATCH /jobs/<id>/highlights/<hid>/ : masquer / réafficher un point clé, ou le classer
    dans une autre catégorie (active, propre à l'organisation ou globale)."""

    hidden = serializers.BooleanField(required=False)
    category = serializers.PrimaryKeyRelatedField(
        queryset=DetectionCategory.objects.none(),
        required=False,
        # Format vérifié avant la requête : un identifiant mal formé donne une erreur 400
        # lisible, pas une exception de la base.
        pk_field=serializers.UUIDField(error_messages={"invalid": "Catégorie invalide."}),
        error_messages={
            "does_not_exist": "Catégorie introuvable pour votre organisation.",
            "incorrect_type": "Catégorie invalide.",
        },
    )

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category"].queryset = DetectionCategory.objects.filter(
            Q(organization=organization) | Q(organization__isnull=True)
        )

    def validate_category(self, category):
        if not category.is_active:
            raise serializers.ValidationError("Cette catégorie est désactivée : choisissez-en une autre.")
        return category

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError("Aucune modification à enregistrer.")
        return attrs
