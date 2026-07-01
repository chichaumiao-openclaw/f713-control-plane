from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import base64
import json
from pathlib import Path
import subprocess
from typing import Any

import requests

from .config import load_settings


API_ROOT = "https://api.github.com"


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


@dataclass
class CachedToken:
    token: str
    expires_at: datetime


_TOKEN_CACHE: CachedToken | None = None


def build_app_jwt() -> str:
    settings = load_settings()
    if not settings.github_app_id or not settings.github_app_pem_path:
        raise RuntimeError("Missing GITHUB_APP_ID or GITHUB_APP_PEM_PATH")
    key_path = Path(settings.github_app_pem_path).expanduser()
    if not key_path.exists():
        raise RuntimeError(f"GitHub App PEM not found: {key_path}")

    now = datetime.now(timezone.utc)
    header = _b64url(json.dumps({"alg": "RS256", "typ": "JWT"}, separators=(",", ":")).encode("utf-8"))
    payload = _b64url(
        json.dumps(
            {
                "iat": int((now - timedelta(seconds=60)).timestamp()),
                "exp": int((now + timedelta(minutes=9)).timestamp()),
                "iss": settings.github_app_id,
            },
            separators=(",", ":"),
        ).encode("utf-8")
    )
    signing_input = f"{header}.{payload}"
    result = subprocess.run(
        ["openssl", "dgst", "-binary", "-sha256", "-sign", str(key_path)],
        input=signing_input.encode("utf-8"),
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="ignore").strip()
        raise RuntimeError(f"openssl signing failed: {stderr or result.returncode}")
    signature = _b64url(result.stdout)
    return f"{signing_input}.{signature}"


def get_installation_token(force_refresh: bool = False) -> str:
    global _TOKEN_CACHE
    settings = load_settings()
    if not settings.github_app_installation_id:
        raise RuntimeError("Missing GITHUB_APP_INSTALLATION_ID")
    if not force_refresh and _TOKEN_CACHE is not None:
        if datetime.now(timezone.utc) + timedelta(minutes=2) < _TOKEN_CACHE.expires_at:
            return _TOKEN_CACHE.token

    jwt_token = build_app_jwt()
    response = requests.post(
        f"{API_ROOT}/app/installations/{settings.github_app_installation_id}/access_tokens",
        headers={
            "Authorization": f"Bearer {jwt_token}",
            "Accept": "application/vnd.github+json",
        },
        timeout=30,
    )
    response.raise_for_status()
    payload: dict[str, Any] = response.json()
    token = str(payload["token"])
    expires_at = datetime.fromisoformat(str(payload["expires_at"]).replace("Z", "+00:00"))
    _TOKEN_CACHE = CachedToken(token=token, expires_at=expires_at)
    return token

