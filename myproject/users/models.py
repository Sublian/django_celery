# users\models.py
from django.contrib.auth.models import AbstractUser
from django.db import models

DOCUMENT_TYPES = [
    ("dni", "DNI"),
    ("ruc", "RUC"),
    ("ce", "Carnet de Extranjería"),
    ("pasaporte", "Pasaporte"),
    ("otro", "Otro"),
]


class User(AbstractUser):
    username = models.CharField(
        max_length=150, unique=True, verbose_name="Nombre de Usuario"
    )
    phone = models.CharField(max_length=20, blank=True, null=True)
    document_type = models.CharField(
        max_length=20,
        choices=DOCUMENT_TYPES,
        default="dni",
        verbose_name="Tipo de Documento",
    )
    document_number = models.CharField(
        max_length=20, unique=True, verbose_name="Número de Documento"
    )
    partner = models.OneToOneField(
        "billing.Partner",
        on_delete=models.CASCADE,
        related_name="user_account",
        null=True,
        blank=True,
    )

    # Si quieres que Django use el campo username para login
    USERNAME_FIELD = "username"
    REQUIRED_FIELDS = ["email"]

    def __str__(self):
        return f"{self.username} ({self.get_document_type_display()} {self.document_number})"

    def deactivate(self):
        """Desactiva el usuario sin eliminarlo."""
        self.is_active = False
        self.save(update_fields=["is_active"])

    def activate(self):
        """Activa el usuario."""
        self.is_active = True
        self.save(update_fields=["is_active"])
