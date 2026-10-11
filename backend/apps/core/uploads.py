"""Validation des fichiers déposés par les clients (documents sources, justificatifs).

Le nom et le Content-Type envoyés par le navigateur ne sont jamais crus : le type réel
est lu dans les premiers octets du fichier (signature « magique »), puis confirmé en
ouvrant le fichier (Pillow pour les images, PDFium pour les PDF). Le fichier est ensuite
renommé avec l'extension du type DÉTECTÉ : un « article.pdf » qui contient du HTML est
refusé, et une photo nommée « photo.html » est stockée (et servie) en « .jpg ».
"""
import logging
import threading
from dataclasses import dataclass
from pathlib import PurePath

from rest_framework import serializers

logger = logging.getLogger(__name__)

HEADER_SIZE = 64


@dataclass(frozen=True)
class FileType:
    code: str
    label: str
    extension: str
    content_type: str
    is_image: bool
    # Formats que Pillow annonce à l'ouverture (images seulement).
    pillow_formats: tuple = ()


PDF = FileType("pdf", "PDF", ".pdf", "application/pdf", False)
# MPO : JPEG « multi-images » produit par certains téléphones (photo + carte de profondeur).
JPEG = FileType("jpeg", "JPG", ".jpg", "image/jpeg", True, ("JPEG", "MPO"))
PNG = FileType("png", "PNG", ".png", "image/png", True, ("PNG",))
WEBP = FileType("webp", "WebP", ".webp", "image/webp", True, ("WEBP",))
HEIC = FileType("heic", "HEIC", ".heic", "image/heic", True, ("HEIF",))
HEIF = FileType("heif", "HEIF", ".heif", "image/heif", True, ("HEIF",))

# Documents sources d'une revue : PDF ou photo de coupure de presse.
SOURCE_DOCUMENT_TYPES = (PDF, JPEG, PNG, WEBP, HEIC, HEIF)
# Justificatif de paiement : PDF, JPG ou PNG.
PAYMENT_PROOF_TYPES = (PDF, JPEG, PNG)

# Marques « ftyp » (conteneur ISO BMFF) des photos iPhone / Android en HEIC-HEIF.
_HEIC_BRANDS = {b"heic", b"heix", b"heim", b"heis", b"hevc", b"hevx", b"hevm", b"hevs"}
_HEIF_BRANDS = {b"mif1", b"msf1"}
_AVIF_BRANDS = {b"avif", b"avis"}

# PDFium n'est pas prévu pour être appelé depuis plusieurs threads à la fois.
_pdfium_lock = threading.Lock()


class UploadRejected(Exception):
    """Fichier refusé ; le message est destiné à l'utilisateur."""


def _read_header(upload, size=HEADER_SIZE):
    upload.seek(0)
    header = upload.read(size)
    upload.seek(0)
    return header or b""


def _iso_bmff_brands(header):
    """Marque principale + marques compatibles de la boîte « ftyp » (HEIC, HEIF, AVIF…)."""
    if header[4:8] != b"ftyp":
        return b"", set()
    box_size = int.from_bytes(header[0:4], "big")
    end = min(box_size, len(header)) if box_size >= 16 else len(header)
    compatible = {header[i:i + 4] for i in range(16, end - 3, 4)}
    return header[8:12], compatible


def detect_file_type(upload):
    """Type réel d'après les premiers octets, ou None si le format n'est pas pris en charge."""
    header = _read_header(upload)
    if header.startswith(b"%PDF-"):
        return PDF
    if header.startswith(b"\xff\xd8\xff"):
        return JPEG
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return PNG
    if header[0:4] == b"RIFF" and header[8:12] == b"WEBP":
        return WEBP
    major, compatible = _iso_bmff_brands(header)
    if major and major not in _AVIF_BRANDS:
        brands = {major} | compatible
        if brands & _HEIC_BRANDS:
            return HEIC
        if brands & _HEIF_BRANDS:
            return HEIF
    return None


def _register_heif_opener():
    try:  # pragma: no cover - dépend de l'environnement
        import pillow_heif

        pillow_heif.register_heif_opener()
    except Exception:  # noqa: BLE001
        logger.info("pillow-heif indisponible : les photos HEIC/HEIF ne pourront pas être vérifiées.")


def _verify_pdf(upload):
    import pypdfium2 as pdfium

    if hasattr(upload, "temporary_file_path"):
        source = upload.temporary_file_path()  # gros fichier déjà écrit sur disque par Django
    else:
        upload.seek(0)
        source = upload.read()
    try:
        with _pdfium_lock:
            document = pdfium.PdfDocument(source)
            try:
                page_count = len(document)
            finally:
                document.close()
    except Exception as exc:  # noqa: BLE001 - PdfiumError, fichier tronqué, protégé…
        raise UploadRejected("Ce PDF est illisible, endommagé ou protégé par un mot de passe.") from exc
    finally:
        upload.seek(0)
    if page_count < 1:
        raise UploadRejected("Ce PDF ne contient aucune page.")


def _verify_image(upload, file_type):
    from PIL import Image

    if file_type in (HEIC, HEIF):
        _register_heif_opener()
    upload.seek(0)
    try:
        with Image.open(upload) as image:
            pillow_format = image.format
            image.verify()
    except Image.DecompressionBombError as exc:
        raise UploadRejected("Cette image est trop grande (nombre de pixels excessif).") from exc
    except Exception as exc:  # noqa: BLE001 - UnidentifiedImageError, fichier tronqué…
        raise UploadRejected("Cette image est illisible ou endommagée.") from exc
    finally:
        upload.seek(0)
    if pillow_format not in file_type.pillow_formats:
        raise UploadRejected("Le contenu de cette image ne correspond pas à son format.")


def validate_upload(upload, *, allowed_types, max_size, formats_message):
    """Vérifie un fichier téléversé et le prépare au stockage.

    Lève UploadRejected (message lisible) si le fichier est vide, trop gros, d'un type non
    autorisé ou illisible. Sinon, renomme le fichier avec l'extension du type détecté et
    retourne ce FileType ; le nom d'origine reste disponible dans `upload.original_name`."""
    if not upload.size:
        raise UploadRejected("Le fichier est vide.")
    if upload.size > max_size:
        raise UploadRejected(f"Le fichier dépasse la taille maximale de {max_size // (1024 * 1024)} Mo.")

    file_type = detect_file_type(upload)
    if file_type is None or file_type not in allowed_types:
        raise UploadRejected(formats_message)
    if file_type.is_image:
        _verify_image(upload, file_type)
    else:
        _verify_pdf(upload)

    original_name = upload.name or ""
    upload.original_name = original_name
    upload.file_type = file_type
    upload.name = f"{PurePath(original_name).stem or 'document'}{file_type.extension}"
    upload.content_type = file_type.content_type
    return file_type


class VerifiedFileField(serializers.FileField):
    """FileField DRF qui n'accepte que les types autorisés, détectés dans les octets.

    Le fichier validé porte `original_name` (nom choisi par l'utilisateur, pour
    l'affichage) et `file_type` (FileType détecté) ; son `name` porte désormais
    l'extension du type réel, reprise telle quelle par les fonctions `upload_to`."""

    def __init__(self, *, allowed_types, max_size, formats_message, **kwargs):
        self.allowed_types = tuple(allowed_types)
        self.max_size = max_size
        self.formats_message = formats_message
        super().__init__(**kwargs)

    def to_internal_value(self, data):
        upload = super().to_internal_value(data)
        try:
            validate_upload(
                upload,
                allowed_types=self.allowed_types,
                max_size=self.max_size,
                formats_message=self.formats_message,
            )
        except UploadRejected as exc:
            raise serializers.ValidationError(str(exc)) from exc
        return upload
