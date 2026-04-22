from django.urls import path
from . import views

app_name = "bots"

urlpatterns = [
    path("dashboard/", views.dashboard, name="dashboard"),
    path("<int:bot_id>/", views.bot_detail, name="detail"),
    path("conversations/<int:conversation_id>/", views.conversation_detail, name="conversation_detail"),
    path("webhooks/whatsapp/inbound/", views.webhook_inbound, name="webhook_inbound"),
    path("webhooks/whatsapp/outbound/", views.webhook_outbound, name="webhook_outbound"),
    path("webhooks/whatsapp/status/", views.webhook_status, name="webhook_status"),
    path("webhooks/whatsapp/error/", views.webhook_error, name="webhook_error"),
]
