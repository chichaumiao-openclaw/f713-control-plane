from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


TASK_STATES = {
    "draft",
    "approved",
    "queued",
    "running",
    "review_ready",
    "human_gate",
    "closed",
    "blocked",
    "cancelled",
}


@dataclass
class TaskRuntimeState:
    task_id: str
    state: str = "approved"
    retries: int = 0
    last_progress_marker: str = ""
    last_worker_status: str = ""
    continuation_count: int = 0
    notification_status: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class CommandRecord:
    command_id: str
    task_id: str
    action: str
    requested_by: str
    payload: dict[str, Any]
