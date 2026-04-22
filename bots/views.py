import json

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from core.models import (
    Bot,
    BotAssignment,
    ClientAccount,
    ClientUserMembership,
    Conversation,
    EndUser,
    ErrorLog,
    Message,
)


ALLOWED_USER_MANAGEMENT_EMAILS = {
    "frederick@datadicoco.com",
    "mafe@datadicoco.com",
}
OPEN_CONVERSATION_STATUSES = {"OPEN", "ABIERTA", "ACTIVE"}


def _user_membership(user):
    return (
        ClientUserMembership.objects.filter(user=user)
        .select_related("client_account")
        .first()
    )


def _accessible_bots(user):
    if user.role in {"ADMIN", "DEV"}:
        return Bot.objects.all()

    membership = _user_membership(user)
    if not membership:
        return Bot.objects.none()

    return Bot.objects.filter(
        botassignment__client_account=membership.client_account,
        botassignment__is_active=True,
        botassignment__revoked_at__isnull=True,
    ).distinct()


def _accessible_conversation_queryset(user):
    bots = _accessible_bots(user)
    return (
        Conversation.objects.filter(bot__in=bots)
        .select_related("bot", "end_user", "client_account")
    )


def _build_dashboard_context(user):
    bots = _accessible_bots(user).order_by("-created_at")
    conversations = (
        _accessible_conversation_queryset(user)
        .order_by("-last_activity_at", "-started_at")[:5]
    )

    membership = _user_membership(user)
    client_account = membership.client_account if membership else None
    accessible_conversations = _accessible_conversation_queryset(user)

    return {
        "bots": bots,
        "recent_conversations": conversations,
        "role": user.role,
        "client_account": client_account,
        "stats": {
            "bots": bots.count(),
            "conversations": accessible_conversations.count(),
            "clients": ClientAccount.objects.count() if user.role in {"ADMIN", "DEV"} else 1,
            "messages": Message.objects.filter(conversation__in=accessible_conversations).count(),
        },
        "can_manage_users": user.email.lower() in ALLOWED_USER_MANAGEMENT_EMAILS,
        "can_manage_clients": user.role in {"ADMIN", "DEV"},
    }


def _json_error(message, status=400):
    return JsonResponse({"ok": False, "error": message}, status=status)


def _parse_json_body(request):
    try:
        return json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return None


def _validate_webhook_secret(request):
    expected_secret = getattr(settings, "N8N_WEBHOOK_SECRET", "")
    if not expected_secret:
        return True
    received_secret = request.headers.get("X-Cocobots-Webhook-Secret", "")
    return received_secret == expected_secret


def _resolve_bot(bot_external_id=None, bot_id=None, business_phone_number_id=None):
    if bot_id:
        return Bot.objects.filter(id=bot_id).first()
    if bot_external_id:
        return Bot.objects.filter(bot_external_id=bot_external_id).first()
    if business_phone_number_id:
        return Bot.objects.filter(external_phone_number_id=business_phone_number_id).first()
    return None


def _resolve_client_account(bot, payload):
    client_account_id = payload.get("client_account_id")
    if client_account_id:
        return get_object_or_404(ClientAccount, id=client_account_id)

    assignments = BotAssignment.objects.filter(
        bot=bot,
        is_active=True,
        revoked_at__isnull=True,
    ).select_related("client_account")

    assignment_count = assignments.count()
    if assignment_count == 1:
        return assignments.first().client_account
    if assignment_count > 1:
        return None
    return None


def _find_or_create_end_user(payload):
    end_user_data = payload.get("end_user", {})
    external_id = end_user_data.get("external_id")
    if not external_id:
        return None

    defaults = {
        "display_name": end_user_data.get("display_name", external_id),
        "channel_type": payload.get("channel_type", "whatsapp"),
        "metadata": {
            "provider": payload.get("provider", "n8n"),
            "raw_payload_present": bool(payload.get("raw_payload")),
        },
    }
    end_user, _ = EndUser.objects.get_or_create(
        external_id=external_id,
        defaults=defaults,
    )

    updated = False
    display_name = end_user_data.get("display_name")
    if display_name and end_user.display_name != display_name:
        end_user.display_name = display_name
        updated = True
    channel_type = payload.get("channel_type", "whatsapp")
    if channel_type and end_user.channel_type != channel_type:
        end_user.channel_type = channel_type
        updated = True
    if updated:
        end_user.save(update_fields=["display_name", "channel_type"])
    return end_user


@login_required
def dashboard(request):
    return render(request, "bots/dashboard.html", _build_dashboard_context(request.user))


@login_required
def bot_detail(request, bot_id):
    bot = get_object_or_404(_accessible_bots(request.user), id=bot_id)
    conversations = (
        _accessible_conversation_queryset(request.user)
        .filter(bot=bot)
        .order_by("-last_activity_at", "-started_at")
    )

    return render(
        request,
        "bots/bot_detail.html",
        {
            "bot": bot,
            "conversations": conversations,
            "role": request.user.role,
        },
    )


@login_required
def conversation_detail(request, conversation_id):
    conversation = get_object_or_404(
        _accessible_conversation_queryset(request.user),
        id=conversation_id,
    )
    messages = conversation.message_set.select_related("sent_by_user").order_by("created_at", "id")

    return render(
        request,
        "bots/conversation_detail.html",
        {
            "conversation": conversation,
            "bot": conversation.bot,
            "messages": messages,
            "conversation_is_open": (conversation.status or "").upper() in OPEN_CONVERSATION_STATUSES,
            "role": request.user.role,
        },
    )


@csrf_exempt
@require_POST
def webhook_inbound(request):
    if not _validate_webhook_secret(request):
        return _json_error("Webhook secret invalido.", status=403)

    payload = _parse_json_body(request)
    if payload is None:
        return _json_error("JSON invalido.")

    bot = _resolve_bot(
        bot_external_id=payload.get("bot_external_id"),
        bot_id=payload.get("bot_id"),
        business_phone_number_id=payload.get("business_phone_number_id"),
    )
    if bot is None:
        return _json_error("Bot no encontrado.")

    end_user = _find_or_create_end_user(payload)
    if end_user is None:
        return _json_error("El payload requiere end_user.external_id.")

    external_thread_id = payload.get("external_thread_id") or end_user.external_id
    client_account = _resolve_client_account(bot, payload)
    if (
        client_account is None
        and BotAssignment.objects.filter(bot=bot, is_active=True, revoked_at__isnull=True).count() > 1
    ):
        return _json_error("El bot esta asignado a multiples clientes; envia client_account_id en el payload.")

    conversation, created = Conversation.objects.get_or_create(
        bot=bot,
        end_user=end_user,
        external_thread_id=external_thread_id,
        defaults={
            "client_account": client_account,
            "channel_type": payload.get("channel_type", "whatsapp"),
            "status": "OPEN",
            "started_at": timezone.now(),
            "last_activity_at": timezone.now(),
        },
    )

    if not created:
        updates = []
        if client_account and conversation.client_account_id != client_account.id:
            conversation.client_account = client_account
            updates.append("client_account")
        if payload.get("channel_type") and conversation.channel_type != payload.get("channel_type"):
            conversation.channel_type = payload.get("channel_type")
            updates.append("channel_type")
        conversation.status = "OPEN"
        conversation.last_activity_at = timezone.now()
        updates.extend(["status", "last_activity_at"])
        conversation.save(update_fields=updates)

    message_data = payload.get("message", {})
    message = Message.objects.create(
        conversation=conversation,
        sent_by_user=None,
        direction=message_data.get("direction", "inbound"),
        sent_by_type=message_data.get("sent_by_type", "end_user"),
        external_message_id=payload.get("external_message_id", ""),
        content=message_data.get("content", ""),
        raw_payload=payload.get("raw_payload", {}),
        created_at=timezone.now(),
        delivery_status=message_data.get("delivery_status", "received"),
        error_code=message_data.get("error_code", ""),
    )

    return JsonResponse(
        {
            "ok": True,
            "conversation_id": conversation.id,
            "message_id": message.id,
            "created_conversation": created,
        },
        status=201 if created else 200,
    )


@csrf_exempt
@require_POST
def webhook_outbound(request):
    if not _validate_webhook_secret(request):
        return _json_error("Webhook secret invalido.", status=403)

    payload = _parse_json_body(request)
    if payload is None:
        return _json_error("JSON invalido.")

    conversation_id = payload.get("conversation_id")
    if conversation_id:
        conversation = Conversation.objects.filter(id=conversation_id).first()
    else:
        bot = _resolve_bot(
            bot_external_id=payload.get("bot_external_id"),
            bot_id=payload.get("bot_id"),
            business_phone_number_id=payload.get("business_phone_number_id"),
        )
        conversation = Conversation.objects.filter(
            bot=bot,
            external_thread_id=payload.get("external_thread_id"),
        ).first()

    if conversation is None:
        return _json_error("Conversacion no encontrada.", status=404)

    message_data = payload.get("message", {})
    message = Message.objects.create(
        conversation=conversation,
        sent_by_user=None,
        direction=message_data.get("direction", "outbound"),
        sent_by_type=message_data.get("sent_by_type", "bot"),
        external_message_id=payload.get("external_message_id", ""),
        content=message_data.get("content", ""),
        raw_payload=payload.get("raw_payload", {}),
        created_at=timezone.now(),
        delivery_status=payload.get("delivery_status", message_data.get("delivery_status", "sent")),
        error_code=message_data.get("error_code", ""),
    )

    conversation.last_activity_at = timezone.now()
    conversation.save(update_fields=["last_activity_at"])

    return JsonResponse(
        {
            "ok": True,
            "conversation_id": conversation.id,
            "message_id": message.id,
        },
        status=201,
    )


@csrf_exempt
@require_POST
def webhook_status(request):
    if not _validate_webhook_secret(request):
        return _json_error("Webhook secret invalido.", status=403)

    payload = _parse_json_body(request)
    if payload is None:
        return _json_error("JSON invalido.")

    message = None
    message_id = payload.get("message_id")
    external_message_id = payload.get("external_message_id")

    if message_id:
        message = Message.objects.filter(id=message_id).first()
    elif external_message_id:
        message = Message.objects.filter(external_message_id=external_message_id).first()
    else:
        return _json_error("Debes enviar message_id o external_message_id.")

    if message is None:
        return _json_error("Mensaje no encontrado.", status=404)

    message.delivery_status = payload.get("delivery_status", message.delivery_status)
    if payload.get("raw_payload") is not None:
        message.raw_payload = payload.get("raw_payload")
    message.save(update_fields=["delivery_status", "raw_payload"])

    return JsonResponse({"ok": True, "message_id": message.id})


@csrf_exempt
@require_POST
def webhook_error(request):
    if not _validate_webhook_secret(request):
        return _json_error("Webhook secret invalido.", status=403)

    payload = _parse_json_body(request)
    if payload is None:
        return _json_error("JSON invalido.")

    conversation = None
    message = None
    conversation_id = payload.get("conversation_id")
    message_id = payload.get("message_id")
    external_message_id = payload.get("external_message_id")

    if conversation_id:
        conversation = Conversation.objects.filter(id=conversation_id).first()
    if message_id:
        message = Message.objects.filter(id=message_id).first()
    elif external_message_id:
        message = Message.objects.filter(external_message_id=external_message_id).first()

    error_log = ErrorLog.objects.create(
        conversation=conversation,
        message=message,
        source=payload.get("source", "n8n_whatsapp"),
        severity=payload.get("severity", "error"),
        error_message=payload.get("message", "Error no especificado"),
        stacktrace=payload.get("stacktrace", ""),
        payload=payload.get("detail", payload),
        created_at=timezone.now(),
    )

    return JsonResponse({"ok": True, "error_log_id": error_log.id}, status=201)
