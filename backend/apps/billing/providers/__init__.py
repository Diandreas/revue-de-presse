from .bank_transfer_provider import BankTransferProvider
from .base import SubscriptionProvider
from .campay_provider import CamPayProvider
from .stripe_provider import StripeProvider

_PROVIDERS = {
    "stripe": StripeProvider,
    "mobile_money": CamPayProvider,
    "bank_transfer": BankTransferProvider,
}


def get_provider(name):
    provider_cls = _PROVIDERS.get(name)
    if provider_cls is None:
        raise ValueError(f"Fournisseur de paiement inconnu : {name}")
    return provider_cls()


__all__ = ["SubscriptionProvider", "StripeProvider", "CamPayProvider", "BankTransferProvider", "get_provider"]
