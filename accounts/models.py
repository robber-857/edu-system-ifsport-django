from django.db import models
from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    class Role(models.TextChoices):
        PARENT = "PARENT", "Parent"
        ASSISTANT = "ASSISTANT", "Assistant"
        ADMIN = "ADMIN", "Admin"
        COACH = "COACH", "Coach"

    role = models.CharField(max_length=16, choices=Role.choices, default=Role.PARENT)
    is_premium = models.BooleanField(default=False)
    phone = models.CharField("Phone", max_length=30, blank=True)  # 新增：可选
    
    def __str__(self):
        return f"{self.username} ({self.role})"

