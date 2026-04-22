from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from core.models import Bot, BotAssignment, ClientAccount, ClientUserMembership

from .forms import BotManagementForm, UserManagementForm

User = get_user_model()
ALLOWED_USER_MANAGEMENT_EMAILS = {
    "frederick@datadicoco.com",
    "mafe@datadicoco.com",
}


def _ensure_dev(user):
    return user.is_authenticated and user.email.lower() in ALLOWED_USER_MANAGEMENT_EMAILS


def _ensure_admin_or_dev(user):
    return user.is_authenticated and user.role in {"ADMIN", "DEV"}


@login_required
def user_management(request):
    if not _ensure_dev(request.user):
        return HttpResponseForbidden("No tienes permisos para administrar usuarios.")

    form = UserManagementForm()

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "create_user":
            form = UserManagementForm(request.POST)
            if form.is_valid():
                _create_user_from_form(form)
                messages.success(request, "Usuario creado correctamente.")
                return redirect("team:user_management")
        elif action == "update_user":
            user = get_object_or_404(User, id=request.POST.get("user_id"))
            new_role = request.POST.get("role")
            is_active = request.POST.get("is_active") == "on"

            if user == request.user and (new_role != "DEV" or not is_active):
                messages.error(request, "No puedes quitarte tu propio acceso DEV ni desactivarte.")
            else:
                user.role = new_role
                user.is_active = is_active
                user.save(update_fields=["role", "is_active"])
                messages.success(request, "Usuario actualizado correctamente.")
            return redirect("team:user_management")

    users = User.objects.all().order_by("-date_joined", "-id")
    client_memberships = {
        membership.user_id: membership.client_account_id
        for membership in ClientUserMembership.objects.select_related("client_account")
    }
    user_rows = [
        {
            "user": user,
            "client_account_id": client_memberships.get(user.id),
        }
        for user in users
    ]
    return render(
        request,
        "team/user_management.html",
        {
            "form": form,
            "user_rows": user_rows,
            "role_choices": User.ROLE_CHOICES,
        },
    )


@login_required
def bot_list(request):
    if not _ensure_admin_or_dev(request.user):
        return HttpResponseForbidden("No tienes permisos para administrar bots.")

    form = BotManagementForm()

    if request.method == "POST":
        form = BotManagementForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Bot creado correctamente.")
            return redirect("team:bot_list")

    bots = Bot.objects.all().order_by("-created_at", "-id")
    return render(
        request,
        "team/bot_list.html",
        {
            "form": form,
            "bots": bots,
        },
    )


@login_required
def client_list(request):
    if not _ensure_admin_or_dev(request.user):
        return HttpResponseForbidden("No tienes permisos para administrar clientes.")

    clients = (
        ClientAccount.objects.all()
        .order_by("-created_at", "-id")
    )
    client_rows = []
    for client in clients:
        active_assignments = BotAssignment.objects.filter(
            client_account=client,
            is_active=True,
            revoked_at__isnull=True,
        )
        client_rows.append(
            {
                "client": client,
                "bot_count": active_assignments.count(),
                "user_count": ClientUserMembership.objects.filter(client_account=client).count(),
            }
        )

    return render(
        request,
        "team/client_list.html",
        {"client_rows": client_rows},
    )


@login_required
def client_detail(request, client_id):
    if not _ensure_admin_or_dev(request.user):
        return HttpResponseForbidden("No tienes permisos para administrar clientes.")

    client_account = get_object_or_404(ClientAccount, id=client_id)

    if request.method == "POST":
        action = request.POST.get("action")
        bot = get_object_or_404(Bot, id=request.POST.get("bot_id"))

        if action == "assign_bot":
            assignment = BotAssignment.objects.filter(
                client_account=client_account,
                bot=bot,
            ).order_by("-assigned_at", "-id").first()

            if assignment and assignment.is_active and assignment.revoked_at is None:
                messages.info(request, "Ese bot ya estaba asignado a este cliente.")
            else:
                if assignment:
                    assignment.is_active = True
                    assignment.revoked_at = None
                    assignment.assigned_by_user = request.user
                    assignment.assigned_at = assignment.assigned_at or timezone.now()
                    assignment.save(
                        update_fields=[
                            "is_active",
                            "revoked_at",
                            "assigned_by_user",
                            "assigned_at",
                        ]
                    )
                else:
                    BotAssignment.objects.create(
                        client_account=client_account,
                        bot=bot,
                        assigned_by_user=request.user,
                        assigned_at=timezone.now(),
                        is_active=True,
                    )
                messages.success(request, "Bot asignado correctamente.")

        elif action == "remove_bot":
            assignment = get_object_or_404(
                BotAssignment,
                client_account=client_account,
                bot=bot,
                is_active=True,
                revoked_at__isnull=True,
            )
            assignment.is_active = False
            assignment.revoked_at = timezone.now()
            assignment.save(update_fields=["is_active", "revoked_at"])
            messages.success(request, "Bot removido correctamente.")

        return redirect("team:client_detail", client_id=client_account.id)

    active_assignments = (
        BotAssignment.objects.filter(
            client_account=client_account,
            is_active=True,
            revoked_at__isnull=True,
        )
        .select_related("bot", "assigned_by_user")
        .order_by("-assigned_at", "-id")
    )
    assigned_bot_ids = list(active_assignments.values_list("bot_id", flat=True))
    available_bots = Bot.objects.exclude(id__in=assigned_bot_ids).order_by("name")
    memberships = (
        ClientUserMembership.objects.filter(client_account=client_account)
        .select_related("user")
        .order_by("user__email")
    )

    return render(
        request,
        "team/client_detail.html",
        {
            "client_account": client_account,
            "active_assignments": active_assignments,
            "available_bots": available_bots,
            "memberships": memberships,
        },
    )


def _create_user_from_form(form):
    nombre = form.cleaned_data["nombre"]
    email = form.cleaned_data["email"]
    password = form.cleaned_data["password"]
    role = form.cleaned_data["role"]
    is_active = form.cleaned_data["is_active"]

    with transaction.atomic():
        user = User.objects.create_user(
            username=email,
            email=email,
            password=password,
            first_name=nombre,
            role=role,
            is_active=is_active,
        )

        if role == "CLIENT":
            client_account = ClientAccount.objects.create(
                nombre_cliente=nombre,
                contacto_principal_email=email,
                estado=is_active,
            )
            ClientUserMembership.objects.create(
                client_account=client_account,
                user=user,
                rol_en_cliente="OWNER",
            )

    return user
