# portal/forms.py

from django import forms
from django.contrib.auth import get_user_model
from .models import Comment
User = get_user_model()

class RegisterForm(forms.Form):
    username = forms.CharField(
        max_length=25,
        label="Username",
        help_text="Required.25 characters or fewer.",
        error_messages={
            "required": "Username is required.",
            "max_length": "Username may be at most 25 characters.",
        },
    )
    accept_terms = forms.BooleanField(
        required=True,
        label="I have read and accept the Terms & Policies"
    )
    #  新增：可选手机号
    phone = forms.CharField(
        required=False,
        label="Phone (optional)",
    )
    email = forms.EmailField(
        required=True,
        label="Email",
        error_messages={
            "invalid": "Enter a valid email address.",
        },
    )
    password = forms.CharField(
        widget=forms.PasswordInput,
        label="Password",
        error_messages={
            "required": "Password is required.",
        },
    )

    def clean_username(self):
        username = self.cleaned_data["username"]
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError("That username is already taken.")
        return username
    # （可选）加一个便捷的方法创建用户
    def create_user(self):
        data = self.cleaned_data
        user = User.objects.create_user(
            username=data["username"],
            email=data["email"],
            password=data["password"],
            is_active=True,
        )
        
        # 如果填写了手机号就保存（你的 User 模型里有 phone 字段）
        phone = data.get("phone") or ""
        if phone:
            user.phone = phone
            user.save()
        return user


class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ["content"]  # 只暴露 content，其他在 view 里填
        widgets = {
            "content": forms.Textarea(attrs={
                "rows": 4,
                "placeholder": "写下您的反馈 ..."
            })
        }
