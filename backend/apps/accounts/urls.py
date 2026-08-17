from django.urls import path

from .views import (
    AcceptInvitationView,
    CookieTokenObtainPairView,
    CookieTokenRefreshView,
    InvitationDetailView,
    InvitationRegisterView,
    InviteView,
    LogoutView,
    MeView,
    OrganizationMeView,
    OrganizationMemberDetailView,
    OrganizationMembersView,
    RegisterView,
)

urlpatterns = [
    path("auth/register/", RegisterView.as_view(), name="auth-register"),
    path("auth/token/", CookieTokenObtainPairView.as_view(), name="auth-token"),
    path("auth/token/refresh/", CookieTokenRefreshView.as_view(), name="auth-token-refresh"),
    path("auth/token/logout/", LogoutView.as_view(), name="auth-logout"),
    path("auth/invitations/<str:token>/", InvitationDetailView.as_view(), name="auth-invitation-detail"),
    path("auth/invitations/<str:token>/accept/", AcceptInvitationView.as_view(), name="auth-invitation-accept"),
    path("auth/invitations/<str:token>/register/", InvitationRegisterView.as_view(), name="auth-invitation-register"),
    path("auth/me/", MeView.as_view(), name="auth-me"),
    path("organizations/me/", OrganizationMeView.as_view(), name="organization-me"),
    path("organizations/me/members/", OrganizationMembersView.as_view(), name="organization-members"),
    path(
        "organizations/me/members/<uuid:membership_id>/",
        OrganizationMemberDetailView.as_view(),
        name="organization-member-detail",
    ),
    path("organizations/me/invite/", InviteView.as_view(), name="organization-invite"),
]
