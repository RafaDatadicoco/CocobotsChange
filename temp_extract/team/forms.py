from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from core.models import Bot

User = get_user_model()


class UserManagementForm(forms.Form):
    nombre = forms.CharField(
        label="Nombre",
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Nombre del usuario",
            }
        ),
    )
    email = forms.EmailField(
        label="Correo electronico",
        widget=forms.EmailInput(
            attrs={
                "class": "form-control",
                "placeholder": "usuario@empresa.com",
            }
        ),
    )
    password = forms.CharField(
        label="Contrasena temporal",
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control",
                "placeholder": "********",
            }
        ),
    )
    role = forms.ChoiceField(
        label="Rol",
        choices=User.ROLE_CHOICES,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    is_active = forms.BooleanField(
        label="Usuario activo",
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )

    def clean_nombre(self):
        nombre = self.cleaned_data["nombre"].strip()
        if len(nombre) < 2:
            raise ValidationError("El nombre debe tener al menos 2 caracteres.")
        return nombre

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email=email).exists():
            raise ValidationError("Ya existe una cuenta con este correo.")
        return email

    def clean_password(self):
        password = self.cleaned_data["password"]
        validate_password(password)
        return password


class BotManagementForm(forms.ModelForm):
    class Meta:
        model = Bot
        fields = [
            "name",
            "description",
            "bot_external_id",
            "external_phone_number_id",
            "status",
            "channel_type",
            "provider",
            "n8n_workflow_id",
            "n8n_webhook_url",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control", "placeholder": "Bot ventas"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 3, "placeholder": "Descripcion funcional del bot"}),
            "bot_external_id": forms.TextInput(attrs={"class": "form-control", "placeholder": "sales-bot-01"}),
            "external_phone_number_id": forms.TextInput(attrs={"class": "form-control", "placeholder": "692795463925349"}),
            "status": forms.TextInput(attrs={"class": "form-control", "placeholder": "ACTIVE"}),
            "channel_type": forms.TextInput(attrs={"class": "form-control", "placeholder": "whatsapp"}),
            "provider": forms.TextInput(attrs={"class": "form-control", "placeholder": "meta_whatsapp"}),
            "n8n_workflow_id": forms.TextInput(attrs={"class": "form-control", "placeholder": "wf_whatsapp_sales_01"}),
            "n8n_webhook_url": forms.URLInput(attrs={"class": "form-control", "placeholder": "https://tu-n8n/webhook/whatsapp-sales"}),
        }

    def clean_bot_external_id(self):
        value = self.cleaned_data["bot_external_id"].strip()
        if Bot.objects.filter(bot_external_id=value).exists():
            raise ValidationError("Ya existe un bot con ese bot_external_id.")
        return value

    def clean_external_phone_number_id(self):
        value = self.cleaned_data["external_phone_number_id"].strip()
        if value and Bot.objects.filter(external_phone_number_id=value).exists():
            raise ValidationError("Ya existe un bot con ese business_phone_number_id.")
        return value
