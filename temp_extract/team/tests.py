from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import Bot, BotAssignment, ClientAccount, ClientUserMembership, CustomUser


class UserManagementTests(TestCase):
    def setUp(self):
        self.dev_user = CustomUser.objects.create_user(
            username="frederick@datadicoco.com",
            email="frederick@datadicoco.com",
            password="ClaveSegura123!",
            role="DEV",
        )
        self.client_user = CustomUser.objects.create_user(
            username="client@example.com",
            email="client@example.com",
            password="ClaveSegura123!",
            role="CLIENT",
        )

    def test_only_dev_can_access_user_management(self):
        self.client.force_login(self.client_user)
        response = self.client.get(reverse("team:user_management"))
        self.assertEqual(response.status_code, 403)

    def test_dev_can_create_client_user_with_membership(self):
        self.client.force_login(self.dev_user)

        response = self.client.post(
            reverse("team:user_management"),
            {
                "action": "create_user",
                "nombre": "Cliente Nuevo",
                "email": "nuevo@example.com",
                "password": "ClaveSegura123!",
                "role": "CLIENT",
                "is_active": "on",
            },
        )

        self.assertRedirects(response, reverse("team:user_management"))
        user = CustomUser.objects.get(email="nuevo@example.com")
        membership = ClientUserMembership.objects.get(user=user)

        self.assertEqual(user.role, "CLIENT")
        self.assertEqual(membership.rol_en_cliente, "OWNER")
        self.assertEqual(ClientAccount.objects.count(), 1)

    def test_dev_can_access_bot_management(self):
        self.client.force_login(self.dev_user)
        response = self.client.get(reverse("team:bot_list"))
        self.assertEqual(response.status_code, 200)

    def test_dev_can_create_bot(self):
        self.client.force_login(self.dev_user)
        response = self.client.post(
            reverse("team:bot_list"),
            {
                "name": "Bot ventas",
                "description": "Bot para WhatsApp",
                "bot_external_id": "sales-bot-01",
                "external_phone_number_id": "692795463925349",
                "status": "ACTIVE",
                "channel_type": "whatsapp",
                "provider": "meta_whatsapp",
                "n8n_workflow_id": "wf_sales_01",
                "n8n_webhook_url": "https://example.com/webhook",
            },
        )

        self.assertRedirects(response, reverse("team:bot_list"))
        self.assertTrue(Bot.objects.filter(bot_external_id="sales-bot-01").exists())


class ClientManagementTests(TestCase):
    def setUp(self):
        self.admin_user = CustomUser.objects.create_user(
            username="admin@example.com",
            email="admin@example.com",
            password="ClaveSegura123!",
            role="ADMIN",
        )
        self.client_user = CustomUser.objects.create_user(
            username="client@example.com",
            email="client@example.com",
            password="ClaveSegura123!",
            role="CLIENT",
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
            description="Bot comercial",
            bot_external_id="bot-ventas",
            status="ACTIVE",
        )

    def test_admin_can_access_client_list(self):
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse("team:client_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Cliente Uno")

    def test_admin_can_assign_bot_to_client(self):
        self.client.force_login(self.admin_user)
        response = self.client.post(
            reverse("team:client_detail", args=[self.client_account.id]),
            {
                "action": "assign_bot",
                "bot_id": self.bot.id,
            },
        )

        self.assertRedirects(response, reverse("team:client_detail", args=[self.client_account.id]))
        self.assertTrue(
            BotAssignment.objects.filter(
                client_account=self.client_account,
                bot=self.bot,
                is_active=True,
                revoked_at__isnull=True,
            ).exists()
        )

    def test_admin_can_remove_bot_from_client(self):
        BotAssignment.objects.create(
            client_account=self.client_account,
            bot=self.bot,
            assigned_by_user=self.admin_user,
            assigned_at=timezone.now(),
            is_active=True,
        )
        self.client.force_login(self.admin_user)

        response = self.client.post(
            reverse("team:client_detail", args=[self.client_account.id]),
            {
                "action": "remove_bot",
                "bot_id": self.bot.id,
            },
        )

        self.assertRedirects(response, reverse("team:client_detail", args=[self.client_account.id]))
        assignment = BotAssignment.objects.get(client_account=self.client_account, bot=self.bot)
        self.assertFalse(assignment.is_active)
        self.assertIsNotNone(assignment.revoked_at)
