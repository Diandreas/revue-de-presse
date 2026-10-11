"""Site public (frontend/) : cohérence des fichiers statiques de référencement et règle
« aucun prix affiché » sur la vitrine et les pages légales.

Tests hermétiques : ils ne lisent que des fichiers du dépôt (pas de réseau, pas de base).
Ignorés si le dossier frontend/ est absent (image Docker du backend seul)."""
import re
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

import pytest
from PIL import Image

REPO = Path(__file__).resolve().parents[2]
FRONTEND = REPO / "frontend"
PUBLIC = FRONTEND / "public"
SRC = FRONTEND / "src"

pytestmark = pytest.mark.skipif(not (SRC / "App.tsx").exists(), reason="frontend/ absent")

# Fichiers qui composent la vitrine et les pages légales (visibles sans compte).
PUBLIC_SOURCES = [
    "routes/LandingPage.tsx",
    "routes/TermsPage.tsx",
    "routes/PrivacyPage.tsx",
    "routes/LegalNoticePage.tsx",
    "components/PublicSite.tsx",
    "components/LegalDocument.tsx",
    "lib/legal.ts",
]

# Montant suivi d'une devise locale : « 50 000 FCFA », « 150.000 F CFA », « 350000 XAF »…
PRICE_PATTERN = re.compile(r"\d[\d\s.,  ]*\s*(?:F\s?CFA|FCFA|XAF|francs?\s+CFA)\b", re.IGNORECASE)


def read(path):
    return path.read_text(encoding="utf-8")


def legal_constant(name):
    match = re.search(rf"export const {name} = '([^']+)'", read(SRC / "lib" / "legal.ts"))
    assert match, f"{name} introuvable dans src/lib/legal.ts"
    return match.group(1)


def app_routes():
    return set(re.findall(r'<Route\s+path="([^"]+)"', read(SRC / "App.tsx")))


class _MetaCollector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.meta = {}
        self.lang = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "html":
            self.lang = attrs.get("lang")
        if tag == "meta" and "content" in attrs:
            key = attrs.get("property") or attrs.get("name")
            if key:
                self.meta[key] = attrs["content"]


def index_meta():
    parser = _MetaCollector()
    parser.feed(read(FRONTEND / "index.html"))
    return parser


def sitemap_urls():
    namespace = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    root = ET.fromstring(read(PUBLIC / "sitemap.xml"))
    return [loc.text.strip() for loc in root.findall("sm:url/sm:loc", namespace)]


@pytest.mark.parametrize("relative_path", PUBLIC_SOURCES)
def test_public_pages_never_show_a_price(relative_path):
    """Décision du propriétaire : tarifs « sur devis », aucun montant sur le site public."""
    source = read(SRC / relative_path)
    assert not PRICE_PATTERN.search(source), PRICE_PATTERN.search(source).group(0)
    assert "price_amount" not in source


def test_landing_page_asks_to_contact_us_for_prices():
    landing = read(SRC / "routes" / "LandingPage.tsx")
    assert "Tarifs : sur devis — contactez-nous" in landing
    assert 'topic="demo"' in landing  # « Demander une démo sur WhatsApp »
    assert 'to="/register"' in landing  # « Essai gratuit 7 jours »


def test_public_and_legal_routes_are_declared_outside_the_authenticated_layout():
    app = read(SRC / "App.tsx")
    protected_start = app.index("<RequireAuth>")
    for path in ("/", "/cgu", "/confidentialite", "/mentions-legales", "/login", "/register"):
        position = app.find(f'<Route path="{path}" ')
        assert 0 <= position < protected_start, f"{path} doit être une route publique"
    for path in ("/dashboard", "/upload", "/billing", "/settings"):
        assert app.find(f'<Route path="{path}" ') > protected_start, f"{path} doit rester protégée"


def test_legal_routes_used_in_footers_exist():
    declared = set(re.findall(r"to: '(/[^']*)'", read(SRC / "lib" / "legal.ts")))
    assert declared == {"/cgu", "/confidentialite", "/mentions-legales"}
    assert declared <= app_routes()


def test_terms_version_and_update_date_are_iso_dates():
    for name in ("TERMS_VERSION", "LEGAL_LAST_UPDATED"):
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", legal_constant(name)), name


def test_index_html_has_sharing_and_seo_meta():
    parser = index_meta()
    meta = parser.meta
    site_url = legal_constant("SITE_URL")
    assert parser.lang == "fr"
    for key in ("description", "og:title", "og:description", "og:url", "og:image", "twitter:title", "twitter:image"):
        assert meta.get(key), f"balise {key} manquante"
    assert meta["twitter:card"] == "summary_large_image"
    # Les robots (WhatsApp, LinkedIn…) exigent une URL d'image absolue.
    assert meta["og:image"] == f"{site_url}/og-image.png"
    assert meta["twitter:image"] == meta["og:image"]
    assert meta["og:url"] == f"{site_url}/"
    assert (meta["og:image:width"], meta["og:image:height"]) == ("1200", "630")


def test_og_image_and_icons_have_the_expected_formats():
    with Image.open(PUBLIC / "og-image.png") as image:
        assert (image.format, image.size) == ("PNG", (1200, 630))
    with Image.open(PUBLIC / "apple-touch-icon.png") as image:
        assert (image.format, image.size) == ("PNG", (180, 180))
    with Image.open(PUBLIC / "favicon.ico") as image:
        assert image.format == "ICO"
    assert (PUBLIC / "favicon.svg").exists()
    # Une image d'aperçu trop lourde n'est pas affichée par WhatsApp (limite ~300 Ko).
    assert (PUBLIC / "og-image.png").stat().st_size < 300 * 1024


def test_sitemap_lists_only_declared_public_routes_on_the_site_origin():
    site = urlparse(legal_constant("SITE_URL"))
    urls = sitemap_urls()
    paths = {urlparse(url).path for url in urls}
    assert {"/", "/cgu", "/confidentialite", "/mentions-legales"} <= paths
    assert all(urlparse(url).netloc == site.netloc and urlparse(url).scheme == "https" for url in urls)
    assert paths <= app_routes()


def test_robots_txt_points_to_the_sitemap_and_hides_the_private_area():
    robots = read(PUBLIC / "robots.txt")
    disallowed = re.findall(r"^Disallow:\s*(\S+)", robots, re.MULTILINE)
    assert f"Sitemap: {legal_constant('SITE_URL')}/sitemap.xml" in robots
    for private in ("/api/", "/admin/", "/dashboard", "/billing", "/settings"):
        assert private in disallowed
    # Aucune page du sitemap ne doit être bloquée.
    for path in {urlparse(url).path for url in sitemap_urls()}:
        assert not any(path.startswith(rule) for rule in disallowed if rule != "/"), path
    assert "/" not in disallowed
