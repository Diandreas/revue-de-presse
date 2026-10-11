"""Fichiers clients privés : liens signés à durée de vie courte.

Les documents déposés, les exports et les justificatifs ne sont plus servis en accès
libre sous /media/. Le stockage par défaut (PrivateMediaStorage) renvoie, à la place de
l'URL publique, un lien signé avec la clé secrète du serveur, lié au chemin du fichier
et valable MEDIA_URL_MAX_AGE secondes au plus :

    /api/media/<expiration>/<signature>/<chemin du fichier>

Le jeton d'accès de l'utilisateur vit en mémoire dans l'application React : une balise
<img> ne peut pas l'envoyer. C'est donc la signature, délivrée uniquement par des
endpoints réservés aux membres de l'organisation, qui fait office d'autorisation.

Le serveur vérifie la signature puis, en production, délègue l'envoi du fichier à nginx
(en-tête X-Accel-Redirect vers un emplacement « internal », cf. ops/nginx/presse-media.conf).
En développement, Django renvoie lui-même le fichier.
"""
import os
import time
from urllib.parse import quote

from django.conf import settings
from django.core import signing
from django.core.exceptions import SuspiciousFileOperation
from django.core.files.storage import FileSystemStorage
from django.http import FileResponse, Http404, HttpResponse, HttpResponseForbidden
from django.urls import reverse
from django.utils._os import safe_join
from django.views.decorators.http import require_safe

SIGNER_SALT = "apps.core.media"

# Types servis : l'extension stockée est celle du type DÉTECTÉ au dépôt (apps.core.uploads)
# ou celle choisie par le serveur (exports). Les anciennes extensions restent servies
# (fichiers déposés avant la validation stricte), tout le reste part en binaire.
MEDIA_CONTENT_TYPES = {
    ".pdf": "application/pdf",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".heic": "image/heic",
    ".heif": "image/heif",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".gif": "image/gif",
    ".bmp": "image/bmp",
    ".tif": "image/tiff",
    ".tiff": "image/tiff",
}
# Affichés dans le navigateur (aperçus) ; tout le reste est proposé au téléchargement.
INLINE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
# Même si un fichier piégé passait la validation, le navigateur le traite comme un
# document isolé (origine opaque, aucun script, aucun accès aux cookies ni à l'appli).
MEDIA_CONTENT_SECURITY_POLICY = "default-src 'none'; style-src 'unsafe-inline'; sandbox"

EXPIRED_LINK_MESSAGE = "Lien expiré ou invalide : rouvrez le document depuis l'application."


def _signer():
    return signing.Signer(salt=SIGNER_SALT)


def _expiry(now=None):
    """Échéance commune à tous les liens émis dans une même fenêtre (un tiers de la durée
    de vie) : l'URL d'un aperçu reste identique d'un rafraîchissement à l'autre, le
    navigateur garde donc l'image en cache au lieu de la retélécharger à chaque polling.
    Un lien reste valable entre 2/3 et 3/3 de MEDIA_URL_MAX_AGE."""
    max_age = settings.MEDIA_URL_MAX_AGE
    window = max(max_age // 3, 1)
    now = int(time.time() if now is None else now)
    return now - now % window + max_age


def _signature(name, expires):
    return _signer().signature(f"{name}:{expires}")


def signed_media_url(name, *, now=None):
    """Chemin signé (relatif à la racine du site) donnant accès au fichier `name`."""
    expires = _expiry(now)
    return reverse(
        "media-signed", kwargs={"expires": expires, "signature": _signature(name, expires), "path": name}
    )


def verify_media_signature(name, expires, signature, *, now=None):
    now = time.time() if now is None else now
    if expires < now:
        return False
    try:
        # unsign() compare en temps constant et accepte aussi SECRET_KEY_FALLBACKS.
        _signer().unsign(f"{name}:{expires}:{signature}")
    except signing.BadSignature:
        return False
    return True


class PrivateMediaStorage(FileSystemStorage):
    """Stockage disque des fichiers clients ; `url()` renvoie un lien signé (jamais /media/)."""

    def url(self, name):
        if name is None:
            raise ValueError("Ce fichier n'a pas de nom.")
        return signed_media_url(name.replace("\\", "/"))


def _apply_protective_headers(response, extension, expires):
    response["Content-Disposition"] = "inline" if extension in INLINE_EXTENSIONS else "attachment"
    response["X-Content-Type-Options"] = "nosniff"
    response["Content-Security-Policy"] = MEDIA_CONTENT_SECURITY_POLICY
    response["Referrer-Policy"] = "no-referrer"
    response["Cache-Control"] = f"private, max-age={max(0, int(expires - time.time()))}"
    return response


@require_safe
def serve_signed_media(request, expires, signature, path):
    if not verify_media_signature(path, expires, signature):
        return HttpResponseForbidden(EXPIRED_LINK_MESSAGE, content_type="text/plain; charset=utf-8")
    try:
        full_path = safe_join(settings.MEDIA_ROOT, path)
    except SuspiciousFileOperation as exc:
        raise Http404("Fichier introuvable.") from exc
    if not os.path.isfile(full_path):
        raise Http404("Fichier introuvable.")

    extension = os.path.splitext(path)[1].lower()
    content_type = MEDIA_CONTENT_TYPES.get(extension, "application/octet-stream")
    if settings.MEDIA_X_ACCEL_REDIRECT:
        # nginx envoie le fichier depuis son emplacement « internal » : aucun worker
        # gunicorn n'est bloqué pendant un téléchargement lent (réseau mobile).
        response = HttpResponse(content_type=content_type)
        response["X-Accel-Redirect"] = settings.MEDIA_X_ACCEL_PREFIX.rstrip("/") + "/" + quote(path)
    else:
        response = FileResponse(open(full_path, "rb"), content_type=content_type)  # noqa: SIM115
    return _apply_protective_headers(response, extension, expires)
