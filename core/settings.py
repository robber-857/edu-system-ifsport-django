from pathlib import Path
import environ
import pymysql
import os

pymysql.install_as_MySQLdb()

# /app/core/settings.py → BASE_DIR=/app（容器内）
BASE_DIR = Path(__file__).resolve().parent.parent

# 读取 env 文件（默认 .env，可用 ENV_FILE 覆盖）
ENV_FILE = os.environ.get("ENV_FILE", ".env")
environ.Env.read_env(BASE_DIR / ENV_FILE, overwrite=True)
env = environ.Env(DEBUG=(bool, True))

# ───── 基础 ─────────────────────────────────────────────────────────────
SECRET_KEY = env("SECRET_KEY", default="change-me")
DEBUG = env.bool("DEBUG", default=True)
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])

# 反向代理下正确识别 HTTPS（Caddy 会带 X-Forwarded-Proto）
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True

# ───── URL 前缀（本地空，线上可设为 /portal） ────────────────────────
URL_PREFIX = env("URL_PREFIX", default="")
FORCE_SCRIPT_NAME = URL_PREFIX or None

# 动态生成静态/媒体与登录路径前缀
if URL_PREFIX:
    STATIC_URL = f"{URL_PREFIX}/static/"
    MEDIA_URL = f"{URL_PREFIX}/media/"
    LOGIN_URL = f"{URL_PREFIX}/auth/login/"
    LOGIN_REDIRECT_URL = f"{URL_PREFIX}/parent/"
    LOGOUT_REDIRECT_URL = f"{URL_PREFIX}/"
else:
    STATIC_URL = "/static/"
    MEDIA_URL = "/media/"
    LOGIN_URL = "/auth/login/"
    LOGIN_REDIRECT_URL = "/parent/"
    LOGOUT_REDIRECT_URL = "/"

# ───── 应用与中间件 ────────────────────────────────────────────────────
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "accounts",
    "portal",
    "widget_tweaks",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "core.urls"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ]
        },
    }
]
WSGI_APPLICATION = "core.wsgi.application"

# ───── 数据库 ──────────────────────────────────────────────────────────
DATABASES = {
    "default": env.db("DATABASE_URL", default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}")
}

AUTH_USER_MODEL = "accounts.User"

# ───── 静态/媒体存储 ────────────────────────────────────────────────────
# 容器内 STATIC_ROOT/MEDIA_ROOT → /public/…（docker-compose 已把 ./public 挂载为 /public）
STATIC_ROOT = Path("/public/static")
MEDIA_ROOT = Path("/public/media")
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# ───── 区域/本地化 ─────────────────────────────────────────────────────
LANGUAGE_CODE = "zh-hans"
TIME_ZONE = "Australia/Sydney"
USE_I18N = True
USE_TZ = True

# ───── 安全项（来自 .env） ─────────────────────────────────────────────
CSRF_TRUSTED_ORIGINS = env.list(
    "CSRF_TRUSTED_ORIGINS", default=["https://edu.ifsport.com.au"]
)
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=False)
SECURE_HSTS_SECONDS = 31536000 if not DEBUG else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = not DEBUG
SECURE_HSTS_PRELOAD = not DEBUG

# ───── 媒体走 S3/R2（可选） ────────────────────────────────────────────
if env.bool("USE_S3", default=False):
    DEFAULT_FILE_STORAGE = "storages.backends.s3boto3.S3Boto3Storage"
    AWS_S3_ENDPOINT_URL = env("AWS_S3_ENDPOINT_URL")
    AWS_ACCESS_KEY_ID = env("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY = env("AWS_SECRET_ACCESS_KEY")
    AWS_STORAGE_BUCKET_NAME = env("AWS_STORAGE_BUCKET_NAME")
    AWS_S3_REGION_NAME = env("AWS_S3_REGION_NAME", default="auto")
    AWS_S3_SIGNATURE_VERSION = "s3v4"
    AWS_DEFAULT_ACL = "public-read"
    # 如未单独指定 MEDIA_URL，则使用 endpoint 直链
    if not env("MEDIA_URL", default=""):
        MEDIA_URL = f"https://{AWS_STORAGE_BUCKET_NAME}.{AWS_S3_ENDPOINT_URL.split('//')[1]}/"

# ───── 邮件 ────────────────────────────────────────────────────────────
if DEBUG:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
    DEFAULT_FROM_EMAIL = "Edu Portal <noreply@local.test>"
else:
    EMAIL_BACKEND = env(
        "EMAIL_BACKEND",
        default="django.core.mail.backends.smtp.EmailBackend",
    )
    DEFAULT_FROM_EMAIL = env(
        "DEFAULT_FROM_EMAIL",
        default="Edu Portal <noreply@example.com>",
    )

EMAIL_HOST = env("EMAIL_HOST", default="")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
EMAIL_USE_SSL = env.bool("EMAIL_USE_SSL", default=False)

