from __future__ import annotations

import os
from typing import Any

import requests

from .config import load_settings
from .store import enqueue_notification, pop_pending_notifications


TOKEN_URL = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
MESSAGE_URL = "https://open.feishu.cn/open-apis/im/v1/messages"
MESSAGE_LIST_URL = "https://open.feishu.cn/open-apis/im/v1/messages"


def _token() -> str:
    app_id = os.environ.get("FEISHU_APP_ID", "")
    app_secret = os.environ.get("FEISHU_APP_SECRET", "")
    if not app_id or not app_secret:
        raise RuntimeError("Missing Feishu credentials")
    resp = requests.post(
        TOKEN_URL,
        json={"app_id": app_id, "app_secret": app_secret},
        timeout=30,
    )
    resp.raise_for_status()
    payload = resp.json()
    if payload.get("code") != 0:
        raise RuntimeError(f"Feishu auth failed: {payload}")
    return payload["tenant_access_token"]


def send_text(text: str) -> None:
    settings = load_settings()
    if not settings.feishu_enabled:
        enqueue_notification({"kind": "text", "text": text})
        return
    open_id = os.environ.get("FEISHU_OPEN_ID_OWNER", "")
    if not open_id:
        enqueue_notification({"kind": "text", "text": text})
        return
    token = _token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    payload: dict[str, Any] = {
        "receive_id": open_id,
        "msg_type": "text",
        "content": '{"text": "%s"}' % text.replace('"', '\\"'),
    }
    resp = requests.post(
        f"{MESSAGE_URL}?receive_id_type=open_id",
        json=payload,
        headers=headers,
        timeout=30,
    )
    resp.raise_for_status()


def flush_pending() -> None:
    pending = pop_pending_notifications()
    if not pending:
        return
    failures: list[dict[str, Any]] = []
    for record in pending:
        try:
            if record.get("kind") == "text":
                send_text(record["text"])
        except Exception:
            failures.append(record)
    for record in failures:
        enqueue_notification(record)


def list_messages(*, container_id_type: str = "chat", container_id: str, page_size: int = 20) -> dict[str, Any]:
    token = _token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    resp = requests.get(
        MESSAGE_LIST_URL,
        headers=headers,
        params={
            "container_id_type": container_id_type,
            "container_id": container_id,
            "page_size": page_size,
        },
        timeout=30,
    )
    resp.raise_for_status()
    payload = resp.json()
    if payload.get("code") != 0:
        raise RuntimeError(f"Feishu list messages failed: {payload}")
    return payload
