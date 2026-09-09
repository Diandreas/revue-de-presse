from abc import ABC, abstractmethod


class SubscriptionProvider(ABC):
    """Interface commune aux 3 moyens de paiement. `SubscriptionService` est le seul
    endroit qui touche les modèles ; les providers ne font que parler au monde
    extérieur (Stripe, CamPay) ou générer une facture à réconcilier manuellement."""

    @abstractmethod
    def create_checkout(self, *, organization, plan, subscription):
        """Retourne un dict JSON-sérialisable décrivant comment le frontend doit
        poursuivre le paiement (URL Stripe, référence de collecte CamPay, instructions
        de virement...)."""

    @abstractmethod
    def cancel(self, *, subscription):
        ...
