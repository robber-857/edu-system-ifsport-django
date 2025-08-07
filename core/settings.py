from pathlib import Path
import environ
import pymysql
pymysql.install_as_MySQLdb()

BASE_DIR = Path(__file__).resolve().parent.parent
env = environ.Env(DEBUG=(bool, True))
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("SECRET_KEY", default="change-me")
DEBUG = env.bool("DEBUG", default=True)
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost","127.0.0.1"])

# —— 可切换前缀：本地为空，线上设为 /portal ——
URL_PREFIX = env("URL_PREFIX", default="")       # 本地：""；线上："/portal"
FORCE_SCRIPT_NAME = URL_PREFIX or None
USE_X_FORWARDED_HOST = True

# URL 与静态前缀随 URL_PREFIX 变化
if URL_PREFIX:
    STATIC_URL = f"{URL_PREFIX}/static/"
    MEDIA_URL  = f"{URL_PREFIX}/media/"
    LOGIN_URL  = f"{URL_PREFIX}/auth/login/"
    LOGIN_REDIRECT_URL = f"{URL_PREFIX}/parent/"
    LOGOUT_REDIRECT_URL = f"{URL_PREFIX}/"
else:
    STATIC_URL = "/static/"
    MEDIA_URL  = "/media/"
    LOGIN_URL  = "/auth/login/"
    LOGIN_REDIRECT_URL = "/parent/"
    LOGOUT_REDIRECT_URL = "/"

INSTALLED_APPS = [
    "django.contrib.admin","django.contrib.auth","django.contrib.contenttypes",
    "django.contrib.sessions","django.contrib.messages","django.contrib.staticfiles",
    "rest_framework","accounts","portal","widget_tweaks",
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
TEMPLATES = [{
    "BACKEND":"django.template.backends.django.DjangoTemplates",
    "DIRS":[BASE_DIR / "templates"],
    "APP_DIRS":True,
    "OPTIONS":{"context_processors":[
        "django.template.context_processors.debug",
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
    ]},
}]
WSGI_APPLICATION = "core.wsgi.application"


DATABASES = {
    "default": env.db("DATABASE_URL", default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}")
}

AUTH_USER_MODEL = "accounts.User"

# 静态/媒体目录（不随前缀变化）
#STATIC_ROOT = (BASE_DIR.parent / "static")
#MEDIA_ROOT  = (BASE_DIR.parent / "media")
STATIC_ROOT = BASE_DIR.parent / "public" / "static"
MEDIA_ROOT  = BASE_DIR.parent / "public" / "media"

STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

LANGUAGE_CODE = "zh-hans"
TIME_ZONE = "Australia/Sydney"
USE_I18N = True
USE_TZ = True

# CSRF 来源与安全项——全部走环境变量，方便以后扩域名
CSRF_TRUSTED_ORIGINS = env.list(
    "CSRF_TRUSTED_ORIGINS",
    default=["https://edu.ifsport.com.au"]
)

SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG

# 证书生效后可开启（先别开，等 HTTPS 通了再改 True）
SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=False)

# HSTS 建议证书 OK 后再开启
SECURE_HSTS_SECONDS = 31536000 if not DEBUG else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = not DEBUG
SECURE_HSTS_PRELOAD = not DEBUG

# S3 / R2 存储（示例：Cloudflare R2，兼容 S3）
if env.bool("USE_S3", default=False):
    DEFAULT_FILE_STORAGE = "storages.backends.s3boto3.S3Boto3Storage"
    AWS_S3_ENDPOINT_URL      = env("AWS_S3_ENDPOINT_URL")
    AWS_ACCESS_KEY_ID        = env("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY    = env("AWS_SECRET_ACCESS_KEY")
    AWS_STORAGE_BUCKET_NAME  = env("AWS_STORAGE_BUCKET_NAME")
    AWS_S3_REGION_NAME       = env("AWS_S3_REGION_NAME", default="auto")
    AWS_S3_SIGNATURE_VERSION = "s3v4"
    AWS_DEFAULT_ACL          = "public-read"
    MEDIA_URL                = f"https://{AWS_STORAGE_BUCKET_NAME}.{AWS_S3_ENDPOINT_URL.split('//')[1]}/"
