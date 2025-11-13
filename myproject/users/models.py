# users\models.py
from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    username = models.CharField(max_length=150, unique=True, verbose_name="Nombre de Usuario")
    phone = models.CharField(max_length=20, blank=True, null=True)
    vat = models.CharField(max_length=11, unique=True, verbose_name="RUC")

    # Si quieres que Django use el campo username para login
    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['email']

    def __str__(self):
        return self.username
    
    def deactivate(self):
        """Desactiva el usuario sin eliminarlo."""
        self.is_active = False
        self.save(update_fields=["is_active"])
        
    def activate(self):
        """Activa el usuario."""
        self.is_active = True
        self.save(update_fields=["is_active"])