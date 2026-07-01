from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json
from typing import Any

import yaml

from .config import COMMANDS_PENDING_DIR, COMMANDS_PROCESSED_DIR, LOGS_DIR, PENDING_NOTIFICATIONS, TASKS_DIR
from .models import TaskRuntimeState


def ensure_layout() -> None:
    for path in [TASKS_DIR, COMMANDS_PENDING_DIR, COMMANDS_PROCESSED_DIR, LOGS_DIR]:
        path.mkdir(parents=True, exist_ok=True)
    if not PENDING_NOTIFICATIONS.exists():
        PENDING_NOTIFICATIONS.write_text("[]\n", encoding="utf-8")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def task_dir(task_id: str) -> Path:
    return TASKS_DIR / task_id


def runtime_dir(task_id: str) -> Path:
    return task_dir(task_id) / "runtime"


def manifest_path(task_id: str) -> Path:
    return task_dir(task_id) / "manifest.yaml"


def state_path(task_id: str) -> Path:
    return runtime_dir(task_id) / "state.json"


def events_path(task_id: str) -> Path:
    return runtime_dir(task_id) / "events.ndjson"


def receipt_path(task_id: str) -> Path:
    return runtime_dir(task_id) / "receipt.md"


def blocker_path(task_id: str) -> Path:
    return runtime_dir(task_id) / "blocker.md"


def artifacts_path(task_id: str) -> Path:
    return runtime_dir(task_id) / "artifacts.json"


def load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def write_yaml(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=False), encoding="utf-8")


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def append_event(task_id: str, event_type: str, payload: dict[str, Any]) -> None:
    record = {
        "timestamp": now_iso(),
        "event_type": event_type,
        "payload": payload,
    }
    with events_path(task_id).open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=True) + "\n")


def load_manifest(task_id: str) -> dict[str, Any]:
    return load_yaml(manifest_path(task_id))


def load_state(task_id: str) -> TaskRuntimeState:
    payload = load_json(state_path(task_id), None)
    if payload is None:
        return TaskRuntimeState(task_id=task_id)
    return TaskRuntimeState(**payload)


def save_state(state: TaskRuntimeState) -> None:
    write_json(state_path(state.task_id), state.__dict__)


def list_task_ids() -> list[str]:
    ensure_layout()
    task_ids: list[str] = []
    for path in TASKS_DIR.iterdir():
        if not path.is_dir():
            continue
        if not (path / "manifest.yaml").exists():
            continue
        task_ids.append(path.name)
    return sorted(task_ids)


def init_task_runtime(task_id: str) -> None:
    runtime_dir(task_id).mkdir(parents=True, exist_ok=True)
    if not state_path(task_id).exists():
        save_state(TaskRuntimeState(task_id=task_id))
    if not artifacts_path(task_id).exists():
        write_json(artifacts_path(task_id), {"artifacts": []})
    if not receipt_path(task_id).exists():
        receipt_path(task_id).write_text("", encoding="utf-8")
    if not blocker_path(task_id).exists():
        blocker_path(task_id).write_text("", encoding="utf-8")
    if not events_path(task_id).exists():
        events_path(task_id).write_text("", encoding="utf-8")


def enqueue_notification(record: dict[str, Any]) -> None:
    pending = load_json(PENDING_NOTIFICATIONS, [])
    pending.append(record)
    write_json(PENDING_NOTIFICATIONS, pending)


def pop_pending_notifications() -> list[dict[str, Any]]:
    pending = load_json(PENDING_NOTIFICATIONS, [])
    write_json(PENDING_NOTIFICATIONS, [])
    return pending
