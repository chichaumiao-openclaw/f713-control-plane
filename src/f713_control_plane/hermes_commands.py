from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re

from .config import ROOT, load_settings
from .gitops import commit_all, ensure_identity, ensure_repo, pull_fast_forward, push_with_app_auth
from .notifier import list_messages, send_text
from .store import append_event, ensure_layout, init_task_runtime, manifest_path, task_dir


HERMES_RUNTIME_DIR = ROOT / "runtime" / "hermes"
SEEN_MESSAGES_PATH = HERMES_RUNTIME_DIR / "seen_messages.json"


def _ensure_runtime() -> None:
    HERMES_RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    if not SEEN_MESSAGES_PATH.exists():
        SEEN_MESSAGES_PATH.write_text("[]\n", encoding="utf-8")


def _load_seen() -> set[str]:
    _ensure_runtime()
    return set(json.loads(SEEN_MESSAGES_PATH.read_text(encoding="utf-8")))


def _save_seen(seen: set[str]) -> None:
    SEEN_MESSAGES_PATH.write_text(json.dumps(sorted(seen), indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def _task_id_from_message_id(message_id: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", message_id).strip("-").lower()
    return f"feishu-{cleaned[:48]}"


def _extract_text(item: dict) -> str:
    body = item.get("body", {})
    content = body.get("content", "{}")
    payload = json.loads(content)
    return str(payload.get("text", "")).strip()


def _build_manifest(task_id: str, text: str) -> str:
    settings = load_settings()
    prompt = (
        "You are running on f713 as a Hermes task triggered from Feishu. "
        "Complete the user's request fully in the current repository context if possible. "
        "When done, write a concise final summary suitable for sending back to Feishu.\n\n"
        f"User request from Feishu:\n{text}\n"
    )
    lines = [
        "schema_version: 1",
        f"task_id: {task_id}",
        f'title: "Feishu Hermes task: {text[:80].replace(chr(34), chr(39))}"',
        "task_class: engineering_simple",
        f"project_ref: {settings.hermes_default_project_ref}",
        "created_by: feishu",
        "launch:",
        "  mode: codex_exec",
        f"  working_dir: {settings.hermes_default_working_dir}",
        '  entrypoint: ""',
        f'  prompt: {json.dumps(prompt, ensure_ascii=True)}',
        f"  codex_profile: {settings.codex_profile}",
        "inputs: []",
        "expected_outputs: []",
        "completion_checks:",
        '  - "worker exits 0"',
        "watchdog:",
        "  enabled: true",
        "  interval_min: 5",
        "  max_retries: 3",
        "  stall_cutoff: 2",
        "notify:",
        "  feishu: true",
        "human_gate:",
        "  required: false",
    ]
    return "\n".join(lines) + "\n"


def import_feishu_commands() -> int:
    settings = load_settings()
    if not settings.feishu_inbox_enabled or not settings.feishu_command_chat_id:
        return 0
    ensure_layout()
    ensure_repo()
    ensure_identity()
    pull_fast_forward()
    seen = _load_seen()
    payload = list_messages(container_id=settings.feishu_command_chat_id, page_size=50)
    items = payload.get("data", {}).get("items", [])
    imported = 0
    for item in reversed(items):
        message_id = str(item.get("message_id", "")).strip()
        if not message_id or message_id in seen:
            continue
        text = _extract_text(item)
        if not text:
            seen.add(message_id)
            continue
        prefix = settings.feishu_command_prefix
        if prefix and not text.startswith(prefix):
            seen.add(message_id)
            continue
        if prefix:
            text = text[len(prefix):].strip()
        task_id = _task_id_from_message_id(message_id)
        target = task_dir(task_id)
        if not target.exists():
            target.mkdir(parents=True, exist_ok=False)
            manifest_path(task_id).write_text(_build_manifest(task_id, text), encoding="utf-8")
            init_task_runtime(task_id)
            append_event(task_id, "task_submitted_from_feishu", {"message_id": message_id, "text": text})
            imported += 1
        seen.add(message_id)
    _save_seen(seen)
    if imported:
        commit_all(f"submit: feishu-import-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}")
        if settings.git_push_enabled:
            push_with_app_auth()
        send_text(f"[hermes] imported {imported} Feishu command task(s).")
    return imported
