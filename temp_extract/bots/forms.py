from django import forms
from django.core.exceptions import ValidationError


class MessageForm(forms.Form):
    content = forms.CharField(
        label="Mensaje",
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 3,
                "placeholder": "Escribe una respuesta para la conversacion",
            }
        ),
    )

    def clean_content(self):
        content = self.cleaned_data["content"].strip()
        if not content:
            raise ValidationError("No puedes enviar un mensaje vacio.")
        return content
