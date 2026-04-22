from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.conf import settings

class CustomUserManager(BaseUserManager):
    """Manager personalizado para CustomUser que usa email en lugar de username"""
    
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('El email es obligatorio')
        
        email = self.normalize_email(email)
        # Generar username automáticamente basado en email
        if 'username' not in extra_fields:
            extra_fields['username'] = email.split('@')[0]
        
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', 'ADMIN')

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser debe tener is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser debe tener is_superuser=True.')

        return self.create_user(email, password, **extra_fields)


class ClientAccount(models.Model):
    id = models.AutoField(primary_key=True)
    nombre_cliente = models.CharField(max_length=100)
    contacto_principal_email = models.EmailField()
    estado = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

class CustomUser(AbstractUser):
    ROLE_CHOICES = (
        ("CLIENT", "Cliente"),
        ("ADMIN", "Admin"),
        ("DEV", "Developer"),
    )

    # Username se mantiene pero se auto-genera
    username = models.CharField(max_length=150, unique=True)
    email = models.EmailField(unique=True)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default="CLIENT")
    is_active = models.BooleanField(default=True)
    accepted_terms = models.BooleanField(default=False)

    objects = CustomUserManager()  # ← IMPORTANTE: Agregar el manager personalizado

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []  # No pedir username en createsuperuser

    @property
    def is_client(self):
        return self.role == "CLIENT"

    @property
    def is_admin(self):
        return self.role == "ADMIN"

    @property
    def is_dev(self):
        return self.role == "DEV"

    def can_send_messages(self):
        return self.role in {"CLIENT", "DEV"}

    def __str__(self):
        return f"{self.email} ({self.role})"


class ClientUserMembership(models.Model):
    id = models.AutoField(primary_key=True)

    client_account = models.ForeignKey(
        ClientAccount, on_delete=models.CASCADE, db_column="client_account_id"
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        db_column="user_id"
    )

    rol_en_cliente = models.CharField(max_length=60)

    class Meta:
        unique_together = ("client_account", "user")

class Bot(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=120)
    description = models.TextField()
    bot_external_id = models.CharField(max_length=120)
    status = models.CharField(max_length=40)
    channel_type = models.CharField(max_length=40, default="whatsapp")
    provider = models.CharField(max_length=60, default="n8n")
    n8n_workflow_id = models.CharField(max_length=120, blank=True)
    n8n_webhook_url = models.URLField(blank=True)
    external_phone_number_id = models.CharField(max_length=120, blank=True)
    config = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    # (Opcional si quieres reflejar la relación directa ClientAccount 1 --- 0..1 Bot)
    # Si el diagrama pretende esa relación como real en BD:
    # client_account = models.OneToOneField(
    #     ClientAccount, on_delete=models.SET_NULL, null=True, blank=True, db_column="client_account_id"
    # )


class BotAssignment(models.Model):
    id = models.AutoField(primary_key=True)

    client_account = models.ForeignKey(
        ClientAccount, on_delete=models.CASCADE, db_column="client_account_id"
    )

    bot = models.ForeignKey(
        Bot, on_delete=models.CASCADE, db_column="bot_id"
    )

    assigned_by_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column="assigned_by_user_id"
    )

    assigned_at = models.DateTimeField()
    revoked_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)


class EndUser(models.Model):
    id = models.AutoField(primary_key=True)
    external_id = models.CharField(max_length=120)
    display_name = models.CharField(max_length=120)
    channel_type = models.CharField(max_length=40)
    metadata = models.JSONField()


class Conversation(models.Model):
    id = models.AutoField(primary_key=True)

    # Bot 1 --- * Conversation
    bot = models.ForeignKey(Bot, on_delete=models.CASCADE)

    client_account = models.ForeignKey(
        ClientAccount,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        db_column="client_account_id",
    )

    # EndUser 1 --- * Conversation
    end_user = models.ForeignKey(EndUser, on_delete=models.CASCADE)

    external_thread_id = models.CharField(max_length=120, blank=True)
    channel_type = models.CharField(max_length=40, blank=True)
    status = models.CharField(max_length=40)
    started_at = models.DateTimeField()
    last_activity_at = models.DateTimeField()
    closed_at = models.DateTimeField(null=True, blank=True)


class Message(models.Model):
    id = models.AutoField(primary_key=True)

    # Conversation 1 --- * Message
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE)

    # User (0..1) --- * Message  (sent_by en el diagrama)
    sent_by_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column="sent_by_user_id"
    )

    direction = models.CharField(max_length=20)
    sent_by_type = models.CharField(max_length=20)
    external_message_id = models.CharField(max_length=180, blank=True)
    content = models.TextField()
    raw_payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField()
    delivery_status = models.CharField(max_length=40)
    error_code = models.CharField(max_length=80)


class MessageLog(models.Model):
    id = models.AutoField(primary_key=True)

    # Message 0..1 --- * MessageLog  (nullable según el diagrama)
    message = models.ForeignKey(
        Message, on_delete=models.SET_NULL, null=True, blank=True
    )

    event_type = models.CharField(max_length=60)
    payload = models.JSONField()
    created_at = models.DateTimeField()


class AuditLog(models.Model):
    id = models.AutoField(primary_key=True)

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    action = models.CharField(max_length=80)
    target_type = models.CharField(max_length=80)
    target_id = models.IntegerField()
    details = models.JSONField()
    created_at = models.DateTimeField()


class ErrorLog(models.Model):
    id = models.AutoField(primary_key=True)

    # Conversation 0..1 --- * ErrorLog  (nullable según el diagrama)
    conversation = models.ForeignKey(
        Conversation, on_delete=models.SET_NULL, null=True, blank=True
    )

    # Message 0..1 --- * ErrorLog (tu diagrama muestra conexión desde Message)
    message = models.ForeignKey(
        Message, on_delete=models.SET_NULL, null=True, blank=True
    )

    source = models.CharField(max_length=80)
    severity = models.CharField(max_length=30)
    error_message = models.TextField()
    stacktrace = models.TextField()
    payload = models.JSONField()
    created_at = models.DateTimeField()
    resolved_at = models.DateTimeField(null=True, blank=True)
