import json

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.models import (
    Bot,
    BotAssignment,
    ClientAccount,
    ClientUserMembership,
    Conversation,
    CustomUser,
    EndUser,
    Message,
)


class ConversationReadOnlyTests(TestCase):
    def setUp(self):
        self.client_user = CustomUser.objects.create_user(
            username="client@example.com",
            email="client@example.com",
            password="ClaveSegura123!",
            role="CLIENT",
            accepted_terms=True,
        )
        self.client_account = ClientAccount.objects.create(
            nombre_cliente="Cliente Uno",
            contacto_principal_email="client@example.com",
        )
        ClientUserMembership.objects.create(
            client_account=self.client_account,
            user=self.client_user,
            rol_en_cliente="OWNER",
        )
        self.bot = Bot.objects.create(
            name="Bot ventas",
            description="Bot de prueba",
            bot_external_id="bot-1",
            status="ACTIVE",
        )
        BotAssignment.objects.create(
            client_account=self.client_account,
            bot=self.bot,
            assigned_by_user=self.client_user,
            assigned_at=timezone.now(),
            is_active=True,
        )
        self.end_user = EndUser.objects.create(
            external_id="lead-1",
            display_name="Lead Uno",
            channel_type="whatsapp",
            metadata={"phone": "+57"},
        )
        self.conversation = Conversation.objects.create(
            bot=self.bot,
            client_account=self.client_account,
            end_user=self.end_user,
            external_thread_id="573001112233",
            channel_type="whatsapp",
            status="OPEN",
            started_at=timezone.now(),
            last_activity_at=timezone.now(),
        )

    def test_conversation_detail_is_read_only(self):
        self.client.force_login(self.client_user)
        response = self.client.get(reverse("bots:conversation_detail", args=[self.conversation.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Solo lectura")
        self.assertNotContains(response, "Enviar mensaje")


@override_settings(N8N_WEBHOOK_SECRET="super-secret")
class WhatsappWebhookTests(TestCase):
    def setUp(self):
        self.bot = Bot.objects.create(
            name="Bot ventas",
            description="Bot de prueba",
            bot_external_id="sales-bot-01",
            external_phone_number_id="692795463925349",
            status="ACTIVE",
        )
        self.client_account = ClientAccount.objects.create(
            nombre_cliente="Cliente Uno",
            contacto_principal_email="contacto@example.com",
        )
        BotAssignment.objects.create(
            client_account=self.client_account,
            bot=self.bot,
            assigned_at=timezone.now(),
            is_active=True,
        )

    def _post(self, url_name, payload):
        return self.client.post(
            reverse(url_name),
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_X_COCOBOTS_WEBHOOK_SECRET="super-secret",
        )

    def test_inbound_webhook_creates_conversation_and_message(self):
        response = self._post(
            "bots:webhook_inbound",
            {
                "bot_external_id": "sales-bot-01",
                "channel_type": "whatsapp",
                "provider": "meta_whatsapp",
                "external_thread_id": "573001112233",
                "external_message_id": "wamid-1",
                "end_user": {
                    "external_id": "573001112233",
                    "display_name": "Juan Perez",
                },
                "message": {
                    "content": "Hola",
                    "direction": "inbound",
                    "message_type": "text",
                },
                "raw_payload": {"sample": True},
            },
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(Conversation.objects.count(), 1)
        self.assertEqual(Message.objects.count(), 1)
        conversation = Conversation.objects.get()
        message = Message.objects.get()
        self.assertEqual(conversation.external_thread_id, "573001112233")
        self.assertEqual(message.external_message_id, "wamid-1")
        self.assertEqual(message.direction, "inbound")

    def test_inbound_webhook_can_resolve_bot_by_business_phone_number_id(self):
        response = self._post(
            "bots:webhook_inbound",
            {
                "channel_type": "whatsapp",
                "provider": "meta_whatsapp",
                "business_phone_number_id": "692795463925349",
                "external_thread_id": "573001112233",
                "external_message_id": "wamid-2",
                "end_user": {
                    "external_id": "573001112233",
                    "display_name": "Juan Perez",
                },
                "message": {
                    "content": "Hola de nuevo",
                    "direction": "inbound",
                    "message_type": "text",
                },
            },
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(Conversation.objects.count(), 1)

    def test_outbound_status_webhooks_update_message_flow(self):
        inbound_response = self._post(
            "bots:webhook_inbound",
            {
                "bot_external_id": "sales-bot-01",
                "channel_type": "whatsapp",
                "external_thread_id": "573001112233",
                "end_user": {
                    "external_id": "573001112233",
                    "display_name": "Juan Perez",
                },
                "message": {
                    "content": "Hola",
                    "direction": "inbound",
                },
            },
        )
        conversation_id = inbound_response.json()["conversation_id"]

        outbound_response = self._post(
            "bots:webhook_outbound",
            {
                "conversation_id": conversation_id,
                "external_message_id": "wamid-out-1",
                "delivery_status": "sent",
                "message": {
                    "content": "Hola, te ayudo con gusto",
                    "direction": "outbound",
                    "sent_by_type": "bot",
                },
            },
        )

        self.assertEqual(outbound_response.status_code, 201)
        message_id = outbound_response.json()["message_id"]
        status_response = self._post(
            "bots:webhook_status",
            {
                "message_id": message_id,
                "delivery_status": "delivered",
                "raw_payload": {"provider_status": "delivered"},
            },
        )

        self.assertEqual(status_response.status_code, 200)
        outbound_message = Message.objects.get(id=message_id)
        self.assertEqual(outbound_message.delivery_status, "delivered")
