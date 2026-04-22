from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.shortcuts import redirect, render

from .forms import LoginForm, SignupForm
from .models import ClientAccount, ClientUserMembership

User = get_user_model()


def index(request):
    if request.user.is_authenticated:
        return redirect("bots:dashboard")
    return render(request, "core/index.html")


def login_view(request):
    form = LoginForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        email = form.cleaned_data["email"]
        password = form.cleaned_data["password"]
        user = authenticate(request, username=email, password=password)

        if user is not None:
            login(request, user)
            return redirect("bots:dashboard")

        if User.objects.filter(email=email, is_active=False).exists():
            form.add_error(None, "Tu cuenta esta inactiva. Contacta a soporte.")
        else:
            form.add_error(None, "Correo o contrasena incorrectos.")

    return render(request, "core/login.html", {"form": form})


def signup(request):
    form = SignupForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        nombre = form.cleaned_data["nombre"]
        email = form.cleaned_data["email"]
        password = form.cleaned_data["password1"]
        accept_terms = form.cleaned_data["accept_terms"]

        try:
            with transaction.atomic():
                user = User.objects.create_user(
                    username=email,
                    email=email,
                    password=password,
                    first_name=nombre,
                    role="CLIENT",
                    accepted_terms=accept_terms,
                )

                client_account = ClientAccount.objects.create(
                    nombre_cliente=nombre,
                    contacto_principal_email=email,
                )

                ClientUserMembership.objects.create(
                    client_account=client_account,
                    user=user,
                    rol_en_cliente="OWNER",
                )

            login(request, user)
            return redirect("bots:dashboard")
        except IntegrityError:
            form.add_error("email", "Ya existe una cuenta con este correo.")

    return render(request, "core/signup.html", {"form": form})


@login_required
def logout_view(request):
    if request.method == "POST":
        logout(request)
    return redirect("core:index")
