"""Construction et mise en file des e-mails transactionnels.

Chaque e-mail est décrit une seule fois (`Email`) puis rendu en texte brut ET en HTML
simple (gabarit notifications/email.html) : les deux versions ne peuvent pas diverger.
L'envoi passe par la tâche Celery `send_email` (réessais espacés, journalisation)."""
import logging
from dataclasses import dataclass, field

from django.conf import settings
from django.contrib.auth import get_user_model
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)

SIGNATURE = "L'équipe Revue de Presse"


@dataclass
class Email:
    subject: str
    paragraphs: list[str]
    greeting: str = "Bonjour,"
    items: list[str] = field(default_factory=list)  # liste à puces (récapitulatifs)
    action_label: str = ""
    action_url: str = ""
    footer: str = ""

    def text(self):
        parts = [self.greeting, *self.paragraphs]
        if self.items:
            parts.append("\n".join(f"- {item}" for item in self.items))
        if self.action_url:
            parts.append(f"{self.action_label} : {self.action_url}")
        parts.append(SIGNATURE)
        if self.footer:
            parts.append(self.footer)
        return "\n\n".join(parts) + "\n"

    def html(self):
        return render_to_string("notifications/email.html", {"email": self, "signature": SIGNATURE})


def whatsapp_digits():
    return "".join(ch for ch in settings.SUPPORT_WHATSAPP_NUMBER if ch.isdigit())


def whatsapp_url():
    return f"https://wa.me/{whatsapp_digits()}"


def frontend_url(path):
    return f"{settings.FRONTEND_BASE_URL.rstrip('/')}{path}"


def admin_url(path):
    return f"{settings.ADMIN_BASE_URL.rstrip('/')}/admin/{path.lstrip('/')}"


def staff_recipients():
    """STAFF_NOTIFICATION_EMAILS, sinon les superusers actifs (petite équipe)."""
    configured = [email for email in settings.STAFF_NOTIFICATION_EMAILS if email]
    if configured:
        return configured
    return list(
        get_user_model()
        .objects.filter(is_superuser=True, is_active=True)
        .exclude(email="")
        .values_list("email", flat=True)
    )


def queue_email(*, to, email, reply_to=None):
    """Met l'e-mail en file (tâche Celery). Si le broker est injoignable, tente un envoi
    direct : un e-mail ne doit jamais se perdre sans laisser de trace dans les journaux.
    Renvoie False si personne n'est à prévenir."""
    from .tasks import send_email

    recipients = sorted({address.strip() for address in to if address and address.strip()})
    if not recipients:
        logger.info("E-mail « %s » sans destinataire : non envoyé.", email.subject)
        return False
    payload = {
        "to": recipients,
        "subject": email.subject,
        "text": email.text(),
        "html": email.html(),
        "reply_to": list(reply_to or []),
    }
    try:
        send_email.delay(**payload)
    except Exception:
        logger.exception("Mise en file impossible pour l'e-mail « %s » : envoi direct.", email.subject)
        from .tasks import deliver_email

        try:
            deliver_email(**payload)
        except Exception:
            logger.exception("Échec de l'envoi direct de l'e-mail « %s » à %s", email.subject, recipients)
            return False
    return True
