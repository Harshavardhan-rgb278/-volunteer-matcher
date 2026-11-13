from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

urlpatterns = [
    # public
    path("", views.drive_list, name="drive_list"),
    path("drives/<int:pk>/", views.drive_detail, name="drive_detail"),
    path("verify/<uuid:code>/", views.certificate_verify, name="certificate_verify"),
    # auth
    path("register/", views.register, name="register"),
    path("login/", auth_views.LoginView.as_view(), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("dashboard/", views.dashboard, name="dashboard"),
    # volunteer portal
    path("volunteer/", views.volunteer_dashboard, name="volunteer_dashboard"),
    path("drives/<int:pk>/signup/", views.drive_signup, name="drive_signup"),
    path("signups/<int:signup_id>/log/", views.log_hours, name="log_hours"),
    path("signups/<int:signup_id>/certificate/", views.certificate_download, name="certificate_download"),
    # manager portal
    path("manager/", views.manager_dashboard, name="manager_dashboard"),
    path("manager/review/<int:pk>/<str:action>/", views.manager_review_action, name="manager_review_action"),
    # non-profit admin portal
    path("organizer/", views.organizer_dashboard, name="organizer_dashboard"),
    path("organizer/drives/new/", views.drive_create, name="drive_create"),
    path("organizer/drives/<int:pk>/edit/", views.drive_edit, name="drive_edit"),
    path("organizer/review/", views.review_logs, name="review_logs"),
    path("organizer/review/<int:pk>/<str:action>/", views.review_log_action, name="review_log_action"),
]
