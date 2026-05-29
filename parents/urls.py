from django.urls import path

from . import views

app_name = "parents"

urlpatterns = [
    path("whatsapp/webhook/", views.whatsapp_webhook, name="whatsapp_webhook"),
]
