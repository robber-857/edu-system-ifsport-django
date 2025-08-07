from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django.utils.translation import gettext_lazy as _
from django.contrib.auth import get_user_model

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

    list_display = ("id", "username", "email", "phone","role", "is_premium",
                    "is_active", "is_staff", "is_superuser", "date_joined")
    list_filter = ("role", "is_premium", "is_active", "is_staff", "is_superuser")
    search_fields = ("username", "email")
    ordering = ("id",)

    fieldsets = (
        (None, {"fields": ("username", "password")}),  # 这里会显示哈希 + “设置密码”链接
        (_("Personal info"), {"fields": ("first_name", "last_name", "email","phone")}),
        (_("Role / Membership"), {"fields": ("role", "is_premium")}),
        (_("Permissions"), {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        (_("Important dates"), {"fields": ("last_login", "date_joined")}),
    )

    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("username", "email", "phone","role", "is_premium", "password1", "password2"),
        }),
    )
