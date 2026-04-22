"""
URL configuration for cocobots project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from pathlib import Path
from bots import views as bot_views

BASE_DIR = Path(__file__).resolve().parent.parent

STATIC_URL = '/static/'

STATICFILES_DIRS = [
    BASE_DIR / 'static',
]

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('core.urls')),
    path('bots/', include('bots.urls')),
    path('team/', include('team.urls')),
    path('webhooks/whatsapp/inbound/', bot_views.webhook_inbound, name='webhook_inbound_root'),
    path('webhooks/whatsapp/outbound/', bot_views.webhook_outbound, name='webhook_outbound_root'),
    path('webhooks/whatsapp/status/', bot_views.webhook_status, name='webhook_status_root'),
    path('webhooks/whatsapp/error/', bot_views.webhook_error, name='webhook_error_root'),
]
