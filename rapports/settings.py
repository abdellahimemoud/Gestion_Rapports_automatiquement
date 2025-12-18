from pathlib import Path

# ===========================
# BASE
# ===========================
BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = 'django-insecure-votre_cle_ici'
DEBUG = True
ALLOWED_HOSTS = []

LANGUAGE_CODE = 'fr'

USE_I18N = True
USE_L10N = True
 
# ===========================
# APPLICATIONS
# ===========================
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # APP
    'app_rapports',

    # API / CORS
    'rest_framework',
    'corsheaders',

    # 🔥 CELERY BEAT (DB Scheduler)
    'django_celery_beat',
]


# ===========================
# MIDDLEWARE
# ===========================
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',

    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',

    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]


# ===========================
# URLS / TEMPLATES
# ===========================
ROOT_URLCONF = 'rapports.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'rapports.wsgi.application'


# ===========================
# DATABASE (MySQL - XAMPP)
# ===========================
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'rapports',
        'USER': 'root',
        'PASSWORD': '',
        'HOST': '127.0.0.1',
        'PORT': '3306',
        'OPTIONS': {
            'init_command': "SET sql_mode='STRICT_TRANS_TABLES'"
        }
    }
}


# ===========================
# EMAIL
# ===========================
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'abdellahisidimedmemoud@gmail.com'
EMAIL_HOST_PASSWORD = 'ghgv ujcf eovu ncqy'  # ⚠️ à mettre dans .env en prod


# ===========================
# STATIC
# ===========================
STATIC_URL = '/static/'


# ===========================
# TIMEZONE (TRÈS IMPORTANT)
# ===========================
USE_TZ = True
TIME_ZONE = "UTC"


# ===========================
# 🔥 CELERY CONFIG (COMPLÈTE)
# ===========================

# Broker (Redis)
CELERY_BROKER_URL = 'redis://127.0.0.1:6379/0'

# Résultats (optionnel mais recommandé)
CELERY_RESULT_BACKEND = 'redis://127.0.0.1:6379/1'

# Sérialisation
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'

# Timezone Celery (OBLIGATOIRE)
CELERY_ENABLE_UTC = True
CELERY_TIMEZONE = TIME_ZONE

# Beat → base de données
CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'

# Fiabilité
CELERY_TASK_ACKS_LATE = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1

# Logging (utile en dev)
CELERY_TASK_TRACK_STARTED = True


# ===========================
# CORS (si frontend séparé)
# ===========================
CORS_ALLOW_ALL_ORIGINS = True
