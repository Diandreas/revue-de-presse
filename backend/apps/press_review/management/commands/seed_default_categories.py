from django.core.management.base import BaseCommand

from apps.press_review.models import DetectionCategory

# Catégories globales d'exemple, génériques et sans contenu juridique réel. Le client
# les affine/complète via /admin/ (apps.press_review.DetectionCategory) au fil de l'eau.
DEFAULT_CATEGORIES = [
    {
        "name": "Risque juridique",
        "type": DetectionCategory.Type.LEGAL_RISK,
        "description": (
            "Contenu pouvant engager une responsabilité juridique au regard du droit "
            "camerounais (presse, diffamation, cybersécurité...). Catégorie générique "
            "à affiner par l'équipe juridique du client."
        ),
        "prompt_hint": (
            "Signale tout passage pouvant constituer un risque juridique (diffamation, "
            "atteinte à la vie privée, incitation, contenu réglementé), sans jamais te "
            "substituer à un avis juridique formel."
        ),
        "keywords": ["diffamation", "cybercriminalité", "presse"],
        "color": "#DC2626",
        "sort_order": 1,
    },
    {
        "name": "Point important",
        "type": DetectionCategory.Type.IMPORTANT_POINT,
        "description": "Information clé pour la direction : décision publique, chiffre marquant, annonce sectorielle.",
        "prompt_hint": "Signale les informations que la direction d'une entreprise devrait connaître en priorité.",
        "keywords": [],
        "color": "#2563EB",
        "sort_order": 2,
    },
    {
        "name": "Intox potentielle",
        "type": DetectionCategory.Type.INTOX,
        "description": (
            "Information dont la fiabilité est douteuse : source non vérifiée, "
            "contradiction avec des faits connus, ton sensationnaliste."
        ),
        "prompt_hint": (
            "Signale les passages qui semblent être de la désinformation ou une intox, "
            "en expliquant pourquoi (source absente, incohérence factuelle, ton alarmiste)."
        ),
        "keywords": ["rumeur", "non confirmé"],
        "color": "#D97706",
        "sort_order": 3,
    },
]


class Command(BaseCommand):
    help = "Crée/actualise les catégories de détection globales par défaut."

    def handle(self, *args, **options):
        for data in DEFAULT_CATEGORIES:
            name = data["name"]
            category, created = DetectionCategory.objects.update_or_create(
                organization=None, name=name, defaults=data
            )
            verb = "Créée" if created else "Mise à jour"
            self.stdout.write(self.style.SUCCESS(f"{verb} : {category.name}"))
