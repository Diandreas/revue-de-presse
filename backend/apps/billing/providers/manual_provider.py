from .base import SubscriptionProvider


class ManualProvider(SubscriptionProvider):
    """Abonnement activé / prolongé à la main par l'équipe (admin Django) après un paiement
    reçu hors ligne. Aucun parcours de paiement côté client, rien à annuler chez un tiers."""

    def create_checkout(self, *, organization, plan, subscription):
        raise ValueError("Les paiements manuels sont enregistrés par l'équipe dans l'administration.")

    def cancel(self, *, subscription):
        return None
