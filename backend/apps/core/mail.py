"""Envoi SMTP avec adresse de réponse par défaut.

Les e-mails partent d'une adresse « no-reply » du domaine authentifié chez le fournisseur
SMTP (Brevo) ; EMAIL_REPLY_TO indique où arrivent les réponses des clients (boîte de
l'équipe). Un message qui fixe déjà son propre Reply-To le garde.
"""

from django.conf import settings
from django.core.mail.backends.smtp import EmailBackend as SMTPEmailBackend


def apply_default_reply_to(messages):
    default = getattr(settings, "EMAIL_REPLY_TO", "")
    if not default:
        return
    for message in messages:
        if not message.reply_to:
            message.reply_to = [default]


class EmailBackend(SMTPEmailBackend):
    def send_messages(self, email_messages):
        apply_default_reply_to(email_messages or [])
        return super().send_messages(email_messages)
