"""Numéros de téléphone (WhatsApp) saisis à l'inscription.

Normalisés au format international « +<indicatif><numéro> » pour qu'un même numéro saisi
de plusieurs façons (« 6 93 42 79 13 », « +237 693-42-79-13 », « 00237693427913 »)
soit reconnu : un seul essai gratuit par numéro."""
import re

CAMEROON_PREFIX = "237"
INVALID_PHONE_MESSAGE = (
    "Numéro de téléphone invalide. Saisissez votre numéro WhatsApp, par exemple 6 93 42 79 13 "
    "ou +237 6 93 42 79 13 (format international pour un numéro hors Cameroun)."
)


def normalize_phone_number(raw):
    """« 6 93 42 79 13 » -> « +237693427913 ». Lève ValueError si le numéro est invalide.

    Un numéro à 9 chiffres sans indicatif est considéré comme camerounais (le marché visé) ;
    tout autre numéro doit être au format international (« + » ou « 00 »)."""
    text = (raw or "").strip()
    digits = re.sub(r"\D", "", text)
    if not text.startswith("+") and digits.startswith("00"):
        digits = digits[2:]
    elif not text.startswith("+") and len(digits) == 9:
        digits = CAMEROON_PREFIX + digits

    if not digits or digits.startswith("0") or not 8 <= len(digits) <= 15:
        raise ValueError(INVALID_PHONE_MESSAGE)
    if digits.startswith(CAMEROON_PREFIX) and len(digits) != len(CAMEROON_PREFIX) + 9:
        raise ValueError(INVALID_PHONE_MESSAGE)
    return f"+{digits}"
