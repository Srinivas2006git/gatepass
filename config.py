import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "unsafe-development-secret-change-me")
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL", f"sqlite:///{BASE_DIR / 'instance' / 'mrit_gate_pass.db'}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_TIME_LIMIT = 3600
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.getenv("FLASK_ENV") == "production"
    REMEMBER_COOKIE_HTTPONLY = True
    SMS_PROVIDER = os.getenv("SMS_PROVIDER", "mock")
    SMS_SENDER_ID = os.getenv("SMS_SENDER_ID", "CP-MRITPR-S")
    SMS_API_BASE_URL = os.getenv("SMS_API_BASE_URL")
    SMS_API_KEY = os.getenv("SMS_API_KEY")
    SMS_DLT_ENTITY_ID = os.getenv("SMS_DLT_ENTITY_ID")
    SMS_DLT_TEMPLATE_ID = os.getenv("SMS_DLT_TEMPLATE_ID")
    PASS_VALIDITY_HOURS = int(os.getenv("PASS_VALIDITY_HOURS", "12"))
    RATELIMIT_STORAGE_URI = os.getenv("RATELIMIT_STORAGE_URI", "memory://")


class TestConfig(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    RATELIMIT_ENABLED = False
    SECRET_KEY = "test-secret"

