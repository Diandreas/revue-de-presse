from django.http import HttpResponse
from django.urls import NoReverseMatch, reverse

from .throttling import AdminLoginRateThrottle, AdminLoginUsernameRateThrottle

TOO_MANY_ADMIN_LOGINS_MESSAGE = "Trop de tentatives de connexion. Réessayez dans quelques minutes."


def _admin_login_path():
    try:
        return reverse("admin:login")
    except NoReverseMatch:
        return None


class AdminLoginThrottleMiddleware:
    """Freine la force brute sur la page de connexion de l'admin Django, qui n'est pas une
    vue DRF : au-delà du taux « admin_login », par IP ou par identifiant saisi, les
    tentatives reçoivent un 429 sans même être vérifiées."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method == "POST" and request.path == _admin_login_path():
            for throttle in (AdminLoginRateThrottle(), AdminLoginUsernameRateThrottle()):
                if not throttle.allow_request(request, None):
                    response = HttpResponse(
                        TOO_MANY_ADMIN_LOGINS_MESSAGE, status=429, content_type="text/plain; charset=utf-8"
                    )
                    wait = throttle.wait()
                    if wait:
                        response["Retry-After"] = str(int(wait) + 1)
                    return response
        return self.get_response(request)
