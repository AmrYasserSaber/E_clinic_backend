from __future__ import annotations

from random import SystemRandom

from django.conf import settings
from django.core.cache import cache


_OTP_PREFIX = "admin-create-otp"
_OTP_RANDOM = SystemRandom()


def _cache_key(email: str) -> str:
    return f"{_OTP_PREFIX}:{email.strip().lower()}"


def otp_ttl_seconds() -> int:
    return int(getattr(settings, "ADMIN_CREATED_USER_OTP_TTL_SECONDS", 900))


def generate_and_store_otp(email: str) -> str:
    otp = f"{_OTP_RANDOM.randint(0, 999999):06d}"
    cache.set(_cache_key(email), otp, timeout=otp_ttl_seconds())
    return otp


def verify_otp(email: str, otp: str) -> bool:
    key = _cache_key(email)
    expected = cache.get(key)
    if not expected or expected != otp:
        return False
    cache.delete(key)
    return True
