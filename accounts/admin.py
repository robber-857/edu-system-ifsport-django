from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django.utils.translation import gettext_lazy as _
from django.contrib.auth import get_user_model
from .models import User

User = get_user_model()

class CustomUserCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email", "role", "is_premium")

class CustomUserChangeForm(UserChangeForm):
    class Meta:
        model = User
        fields = ("username", "email", "first_name", "last_name",
                  "role", "is_premium", "is_active", "is_staff", "is_superuser",
                  "groups", "user_permissions")

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    add_form = CustomUserCreationForm
    form = CustomUserChangeForm

    list_display = ("id", "username", "email", "phone","role", "is_premium","approval_status",
                    "is_active", "is_staff", "is_superuser", "date_joined")
    list_filter = ("role", "is_premium", "is_active", "is_staff", "is_superuser","approval_status")
    search_fields = ("username", "email")
    ordering = ("id",)

    fieldsets = (
        (None, {"fields": ("username", "password")}),  # 这里会显示哈希 + “设置密码”链接
        (_("Personal info"), {"fields": ("first_name", "last_name", "email","phone")}),
        (_("Role / Membership"), {"fields": ("role", "is_premium")}),
        ("Approval",      {"fields": ("approval_status",)}),
        (_("Permissions"), {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        (_("Important dates"), {"fields": ("last_login", "date_joined")}),
    )

    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("username", "email", "phone","role", "is_premium", "password1", "password2"),
        }),
    )

    actions = ["approve_users", "reject_users"]

    @admin.action(description="Mark selected users as APPROVED")
    def approve_users(self, request, qs):
        qs.update(approval_status=User.Approval.APPROVED, is_active=True)

    @admin.action(description="Mark selected users as REJECTED")
    def reject_users(self, request, qs):
        qs.update(approval_status=User.Approval.REJECTED, is_active=False)
