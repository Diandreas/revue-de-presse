from unittest import mock

from django.core.mail import EmailMessage
from django.core.mail.backends.smtp import EmailBackend as SMTPEmailBackend

from apps.core.mail import EmailBackend


def _send(message):
    with mock.patch.object(SMTPEmailBackend, "send_messages", return_value=1) as parent:
        EmailBackend().send_messages([message])
    return parent


def test_default_reply_to_is_added(settings):
    settings.EMAIL_REPLY_TO = "equipe@example.com"
    message = EmailMessage("Sujet", "Corps", "no-reply@example.com", ["client@example.com"])
    parent = _send(message)
    parent.assert_called_once()
    assert message.reply_to == ["equipe@example.com"]


def test_explicit_reply_to_is_kept(settings):
    settings.EMAIL_REPLY_TO = "equipe@example.com"
    message = EmailMessage(
        "Sujet", "Corps", "no-reply@example.com", ["client@example.com"], reply_to=["client@example.com"]
    )
    _send(message)
    assert message.reply_to == ["client@example.com"]


def test_no_default_reply_to_when_unset(settings):
    settings.EMAIL_REPLY_TO = ""
    message = EmailMessage("Sujet", "Corps", "no-reply@example.com", ["client@example.com"])
    _send(message)
    assert message.reply_to == []
