"""
Django settings for kokoland project.
Optimized for both local development and DigitalOcean App Platform.
"""

import os
from pathlib import Path
from datetime import timedelta
from dotenv import load_dotenv
import dj_database_url

# Build paths inside the project like this: BASE_DIR / 'subdir'
BASE_DIR = Path(__file__).resolve().parent.parent

# =====================
# ENVIRONMENT DETECTION & CONFIGURATION
# =====================

# Load environment variables
ENVIRONMENT = os.environ.get('DJANGO_ENV', 'development').lower()

if ENVIRONMENT == 'development':
    # Load .env.local for development
    env_file = BASE_DIR / '.env.local'
    if env_file.exists():
        load_dotenv(env_file)
        print(" Loaded .env.local for development")
    else:
        print(".env.local not found, using environment variables")
else:
    print("Production environment - using DigitalOcean environment variables")

# Detect if running on DigitalOcean
# IS_DIGITALOCEAN = os.environ.get('DIGITALOCEAN_APP_ID') is not None
IS_PRODUCTION = ENVIRONMENT == 'production'# or IS_DIGITALOCEAN
IS_LOCAL = not IS_PRODUCTION

print(f" Environment: {'PRODUCTION' if IS_PRODUCTION else 'LOCAL DEVELOPMENT'}")

# =====================
# SECURITY SETTINGS
# =====================

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get('SECRET_KEY')

if not SECRET_KEY:
    if IS_PRODUCTION:
        raise ValueError("SECRET_KEY environment variable is required in production!")
    else:
        SECRET_KEY = 'django-insecure-dev-key-only-for-local-development'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.environ.get('DEBUG', 'True' if IS_LOCAL else 'False').lower() == 'true'

# Hosts configuration
if IS_PRODUCTION:
    ALLOWED_HOSTS = [
        '.onrender.com',
        # '.ondigitalocean.app',
        'localhost',
        '127.0.0.1',
    ]
    # Add custom domain if provided
    custom_domain = os.environ.get('CUSTOM_DOMAIN')
    if custom_domain:
        ALLOWED_HOSTS.append(custom_domain)
else:
    ALLOWED_HOSTS = ['localhost', '127.0.0.1', '0.0.0.0', '192.168.1.*']

# Security settings for production
if IS_PRODUCTION:
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 31536000  # 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
else:
    SECURE_SSL_REDIRECT = False
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False

# CSRF trusted origins
CSRF_TRUSTED_ORIGINS = [
    'https://*.onrender.com',
    'https://kokoland.onrender.com',
]
if IS_PRODUCTION:
    CSRF_TRUSTED_ORIGINS = [
        'https://*.onrender.com',
        # 'https://*.ondigitalocean.app',
    ]
    custom_domain = os.environ.get('CUSTOM_DOMAIN')
    if custom_domain:
        CSRF_TRUSTED_ORIGINS.append(f'https://{custom_domain}')
else:
    CSRF_TRUSTED_ORIGINS = [
        'http://localhost:8000',
        'http://127.0.0.1:8000',
        'http://localhost:3000',
        'http://127.0.0.1:3000',
    ]

# =====================
# DATABASE CONFIGURATION
# =====================

if IS_PRODUCTION:
    # DigitalOcean provides DATABASE_URL automatically when you add a database
    DATABASE_URL = os.environ.get('DATABASE_URL')
    if DATABASE_URL:
        DATABASES = {
            'default': dj_database_url.config(
                default=DATABASE_URL,
                conn_max_age=600,
                conn_health_checks=True,
                ssl_require=True
            )
        }
    else:
        # Fallback to SQLite if no database is configured
        DATABASES = {
            'default': {
                'ENGINE': 'django.db.backends.sqlite3',
                'NAME': BASE_DIR / 'db.sqlite3',
            }
        }
else:
    # Local development database
    LOCAL_DB_ENGINE = os.environ.get('LOCAL_DB_ENGINE', 'sqlite')
    
    if LOCAL_DB_ENGINE == 'postgresql':
        DATABASES = {
            'default': {
                'ENGINE': 'django.db.backends.postgresql',
                'NAME': os.environ.get('LOCAL_DB_NAME', 'kokoland'),
                'USER': os.environ.get('LOCAL_DB_USER', 'postgres'),
                'PASSWORD': os.environ.get('LOCAL_DB_PASSWORD', '123'),
                'HOST': os.environ.get('LOCAL_DB_HOST', 'localhost'),
                'PORT': os.environ.get('LOCAL_DB_PORT', '5432'),
            }
        }
    else:
        # Default to SQLite for local development
        DATABASES = {
            'default': {
                'ENGINE': 'django.db.backends.sqlite3',
                'NAME': BASE_DIR / 'db.sqlite3',
            }
        }

# =====================
# APPLICATION DEFINITION
# =====================

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Third-party apps
    'corsheaders',
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    
    # Local apps
    'book',
    'user',
    'buying',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',  # First
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'kokoland.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
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

WSGI_APPLICATION = 'kokoland.wsgi.application'


# Cache Configuration (using Redis for production)
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': 'redis://127.0.0.1:6379/1',
    }
}

# File Upload Settings
DATA_UPLOAD_MAX_MEMORY_SIZE = 52428800  # 50MB
FILE_UPLOAD_MAX_MEMORY_SIZE = 52428800  # 50MB
# =====================
# PASSWORD VALIDATION
# =====================

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# =====================
# INTERNATIONALIZATION
# =====================

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# =====================
# STATIC & MEDIA FILES
# =====================

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# WhiteNoise configuration for production
if IS_PRODUCTION:
    STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
else:
    STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.StaticFilesStorage'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# =====================
# REST FRAMEWORK & JWT
# =====================

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticatedOrReadOnly',
        "rest_framework.permissions.AllowAny",
    ],
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ] if not DEBUG else [
        'rest_framework.renderers.JSONRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer',
    ],
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=30),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
    'AUTH_HEADER_TYPES': ('Bearer',),
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
}

# =====================
# CORS SETTINGS
# =====================

if IS_LOCAL:
    # Local development: Allow all origins
    CORS_ALLOW_ALL_ORIGINS = True
    CORS_ALLOWED_ORIGINS = [
        "https://kokoland.onrender.com",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ]

else:
    # Production: Specific origins only
    CORS_ALLOW_ALL_ORIGINS = True
    CORS_ALLOWED_ORIGINS = []
    provided_cors = os.environ.get('CORS_ALLOWED_ORIGINS', '').split(',')
    CORS_ALLOWED_ORIGINS = [origin.strip() for origin in provided_cors if origin.strip()]
    

CORS_ALLOW_CREDENTIALS = True

CORS_ALLOW_METHODS = [
    'DELETE', 'GET', 'OPTIONS', 'PATCH', 'POST', 'PUT',
]

CORS_ALLOW_HEADERS = [
    'accept', 'accept-encoding', 'authorization', 'content-type',
    'dnt', 'origin', 'user-agent', 'x-csrftoken', 'x-requested-with',
]

# =====================
# EMAIL CONFIGURATION
# =====================

    # Production: SMTP backend
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = os.environ.get('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', 587))
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
EMAIL_USE_TLS = os.environ.get('EMAIL_USE_TLS', 'True').lower() == 'true'
DEFAULT_FROM_EMAIL = EMAIL_HOST_USER or 'noreply@kokoland.com'


PASSWORD_RESET_TIMEOUT = 900  # 15 minutes
AUTH_USER_MODEL = 'user.User'

# =====================
# LOGGING CONFIGURATION
# =====================

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'simple' if DEBUG else 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'DEBUG' if DEBUG else 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'django.db.backends': {
            'level': 'DEBUG' if DEBUG else 'INFO',
        },
    },
}

# =====================
# FINAL CONFIGURATION CHECK
# =====================

# print(f"🔧 Configuration Summary:")
# print(f"   Environment: {'PRODUCTION' if IS_PRODUCTION else 'DEVELOPMENT'}")
# print(f"   Debug: {DEBUG}")
# print(f"   Database: {DATABASES['default']['ENGINE']}")
# print(f"   Allowed Hosts: {ALLOWED_HOSTS}")
# print("🎉 Settings loaded successfully!")