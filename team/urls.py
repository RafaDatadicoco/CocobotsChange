from django.urls import path

from . import views

app_name = "team"

urlpatterns = [
    path("users/", views.user_management, name="user_management"),
    path("bots/", views.bot_list, name="bot_list"),
    path("clients/", views.client_list, name="client_list"),
    path("clients/<int:client_id>/", views.client_detail, name="client_detail"),
]
