from __future__ import annotations

import json
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlencode

import requests
from django.conf import settings
from django.core.cache import cache
from django.core.signing import BadSignature, SignatureExpired, TimestampSigner

from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2 import id_token as google_id_token


@dataclass(frozen=True)
class GoogleTokenExchangeResult:
    access_token: str | None
    id_token: str


@dataclass(frozen=True)
class GoogleIdTokenClaims:
    sub: str
    email: str
    email_verified: bool
    given_name: str | None
    family_name: str | None
    nonce: str | None


@dataclass(frozen=True)
class GoogleOneTimeCodePayload:
    jti: str
    sub: str
    email: str
    email_verified: bool
    given_name: str | None
    family_name: str | None
    intent: str


class GoogleOAuthService:
    AUTHORIZATION_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
    TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
    ONE_TIME_CODE_TTL_SECONDS = 300

    def __init__(self) -> None:
        self._client_id: str = settings.GOOGLE_OAUTH_CLIENT_ID
        self._client_secret: str = settings.GOOGLE_OAUTH_CLIENT_SECRET
        self._callback_url: str = settings.GOOGLE_OAUTH_CALLBACK_URL
        self._scopes: list[str] = settings.GOOGLE_OAUTH_SCOPES
        if not self._client_id or not self._client_secret or not self._callback_url:
            raise ValueError("Google OAuth settings are not configured.")
        self._state_signer: TimestampSigner = TimestampSigner(
            key=settings.GOOGLE_OAUTH_STATE_SECRET,
            salt="google-oauth-state",
        )
        self._one_time_code_signer: TimestampSigner = TimestampSigner(
            key=settings.GOOGLE_OAUTH_STATE_SECRET,
            salt="google-oauth-one-time-code",
        )

    def build_authorization_url(self, *, intent: str) -> str:
        nonce: str = secrets.token_urlsafe(16)
        state_token: str = self._sign_state({"intent": intent, "nonce": nonce})
        query = {
            "client_id": self._client_id,
            "redirect_uri": self._callback_url,
            "response_type": "code",
            "scope": " ".join(self._scopes),
            "state": state_token,
            "nonce": nonce,
            "include_granted_scopes": "true",
            "prompt": "select_account",
        }
        return f"{self.AUTHORIZATION_ENDPOINT}?{urlencode(query)}"

    def exchange_code_for_tokens(self, *, code: str) -> GoogleTokenExchangeResult:
        data = {
            "code": code,
            "client_id": self._client_id,
            "client_secret": self._client_secret,
            "redirect_uri": self._callback_url,
            "grant_type": "authorization_code",
        }
        response = requests.post(self.TOKEN_ENDPOINT, data=data, timeout=15)
        response.raise_for_status()
        body: dict[str, Any] = response.json()
        id_token_value: str | None = body.get("id_token")
        if not id_token_value:
            raise ValueError("Google token response did not include id_token.")
        access_token_value = body.get("access_token")
        if access_token_value is not None and not isinstance(access_token_value, str):
            access_token_value = None
        return GoogleTokenExchangeResult(access_token=access_token_value, id_token=id_token_value)

    def verify_id_token(self, *, id_token_value: str, expected_nonce: str) -> GoogleIdTokenClaims:
        claims: dict[str, Any] = google_id_token.verify_oauth2_token(
            id_token_value,
            GoogleAuthRequest(),
            self._client_id,
        )
        email: str | None = claims.get("email")
        if not email or not isinstance(email, str):
            raise ValueError("Google id_token did not include a valid email.")
        sub: str | None = claims.get("sub")
        if not sub or not isinstance(sub, str):
            raise ValueError("Google id_token did not include a valid sub.")
        email_verified = self._parse_email_verified(claims.get("email_verified"))
        given_name = claims.get("given_name")
        family_name = claims.get("family_name")
        nonce = claims.get("nonce")
        nonce_value = str(nonce) if isinstance(nonce, str) else None
        if not nonce_value or nonce_value != expected_nonce:
            raise ValueError("Google id_token nonce validation failed.")
        return GoogleIdTokenClaims(
            sub=sub,
            email=email,
            email_verified=email_verified,
            given_name=str(given_name) if isinstance(given_name, str) else None,
            family_name=str(family_name) if isinstance(family_name, str) else None,
            nonce=nonce_value,
        )

    def create_one_time_code(self, *, payload: GoogleOneTimeCodePayload) -> str:
        serialized: str = json.dumps(self._to_one_time_code_dict(payload), separators=(",", ":"), sort_keys=True)
        return self._one_time_code_signer.sign(serialized)

    def consume_one_time_code(self, *, one_time_code: str) -> GoogleOneTimeCodePayload:
        try:
            serialized: str = self._one_time_code_signer.unsign(
                one_time_code,
                max_age=self.ONE_TIME_CODE_TTL_SECONDS,
            )
        except SignatureExpired as err:
            raise ValueError("One-time code expired.") from err
        except BadSignature as err:
            raise ValueError("Invalid one-time code.") from err

        data = json.loads(serialized)
        if not isinstance(data, dict):
            raise ValueError("Invalid one-time code payload.")
        payload = self._from_one_time_code_dict(data)
        if not self._mark_one_time_code_used(payload.jti):
            raise ValueError("One-time code already used.")
        return payload

    def peek_one_time_code(self, *, one_time_code: str) -> GoogleOneTimeCodePayload:
        try:
            serialized: str = self._one_time_code_signer.unsign(
                one_time_code,
                max_age=self.ONE_TIME_CODE_TTL_SECONDS,
            )
        except SignatureExpired as err:
            raise ValueError("One-time code expired.") from err
        except BadSignature as err:
            raise ValueError("Invalid one-time code.") from err
        data = json.loads(serialized)
        if not isinstance(data, dict):
            raise ValueError("Invalid one-time code payload.")
        return self._from_one_time_code_dict(data)

    def validate_state(self, *, state: str) -> dict[str, Any]:
        try:
            serialized: str = self._state_signer.unsign(state, max_age=600)
        except SignatureExpired as err:
            raise ValueError("State expired.") from err
        except BadSignature as err:
            raise ValueError("Invalid state.") from err
        data = json.loads(serialized)
        if not isinstance(data, dict):
            raise ValueError("Invalid state payload.")
        return data

    def create_state(self, *, intent: str) -> str:
        return self._sign_state({"intent": intent, "nonce": secrets.token_urlsafe(16)})

    def _sign_state(self, data: dict[str, Any]) -> str:
        serialized: str = json.dumps(data, separators=(",", ":"), sort_keys=True)
        return self._state_signer.sign(serialized)

    def _mark_one_time_code_used(self, jti: str) -> bool:
        cache_key = f"google_otc_used:{jti}"
        return bool(cache.add(cache_key, "1", timeout=self.ONE_TIME_CODE_TTL_SECONDS))

    def _to_one_time_code_dict(self, payload: GoogleOneTimeCodePayload) -> dict[str, Any]:
        return {
            "jti": payload.jti,
            "sub": payload.sub,
            "email": payload.email,
            "email_verified": payload.email_verified,
            "given_name": payload.given_name,
            "family_name": payload.family_name,
            "intent": payload.intent,
            "issued_at": datetime.now(tz=timezone.utc).isoformat(),
        }

    def _from_one_time_code_dict(self, data: dict[str, Any]) -> GoogleOneTimeCodePayload:
        required = ["jti", "sub", "email", "email_verified", "intent"]
        for key in required:
            if key not in data:
                raise ValueError("Invalid one-time code payload.")
        jti = data["jti"]
        sub = data["sub"]
        email = data["email"]
        if not isinstance(jti, str) or not isinstance(sub, str) or not isinstance(email, str):
            raise ValueError("Invalid one-time code payload.")
        intent = data["intent"]
        if not isinstance(intent, str):
            raise ValueError("Invalid one-time code payload.")
        email_verified = bool(data.get("email_verified", False))
        given_name_raw = data.get("given_name")
        family_name_raw = data.get("family_name")
        return GoogleOneTimeCodePayload(
            jti=jti,
            sub=sub,
            email=email,
            email_verified=email_verified,
            given_name=str(given_name_raw) if isinstance(given_name_raw, str) else None,
            family_name=str(family_name_raw) if isinstance(family_name_raw, str) else None,
            intent=intent,
        )

    def _parse_email_verified(self, value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized == "true":
                return True
            if normalized == "false":
                return False
        if isinstance(value, int):
            return value == 1
        return False
