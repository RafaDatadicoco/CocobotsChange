from django.test import Client, TestCase
from django.urls import reverse

from .models import ClientAccount, ClientUserMembership, CustomUser


class SignupFlowTests(TestCase):
    def test_signup_creates_client_user_account_and_membership(self):
        response = self.client.post(
            reverse("core:signup"),
            {
                "nombre": "Frederick",
                "email": "frederick@example.com",
                "password1": "ClaveSegura123!",
                "password2": "ClaveSegura123!",
                "accept_terms": True,
            },
        )

        self.assertRedirects(response, reverse("bots:dashboard"))
        user = CustomUser.objects.get(email="frederick@example.com")
        membership = ClientUserMembership.objects.get(user=user)

        self.assertEqual(user.role, "CLIENT")
        self.assertTrue(user.accepted_terms)
        self.assertEqual(membership.rol_en_cliente, "OWNER")
        self.assertEqual(ClientAccount.objects.count(), 1)


class LoginFlowTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_inactive_user_cannot_login(self):
        CustomUser.objects.create_user(
            username="inactive@example.com",
            email="inactive@example.com",
            password="ClaveSegura123!",
            is_active=False,
        )

        response = self.client.post(
            reverse("core:login"),
            {"email": "inactive@example.com", "password": "ClaveSegura123!"},
        )

        self.assertContains(response, "Tu cuenta esta inactiva", status_code=200)
