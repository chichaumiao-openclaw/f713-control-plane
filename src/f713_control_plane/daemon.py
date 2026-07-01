from __future__ import annotations

import shutil
import time
from pathlib import Path

from .config import load_settings
from .engine import launch_task
from .gitops import commit_all, ensure_identity, ensure_repo, pull_fast_forward, push_with_app_auth
from .notifier import flush_pending, send_text
from .store import (
    COMMANDS_PENDING_DIR,
    COMMANDS_PROCESSED_DIR,
    append_event,
    ensure_layout,
    init_task_runtime,
    list_task_ids,
    load_state,
    load_yaml,
    save_state,
)


def apply_command(path: Path) -> None:
    payload = load_yaml(path)
    task_id = payload["task_id"]
    action = payload["action"]
    state = load_state(task_id)
    if action == "resume" and state.state in {"blocked", "review_ready", "human_gate"}:
        state.state = "approved"
        state.last_worker_status = "resumed_by_command"
        save_state(state)
        append_event(task_id, "command_resume", {"command_id": payload["command_id"]})
    elif action == "cancel":
        state.state = "cancelled"
        state.last_worker_status = "cancelled_by_command"
        save_state(state)
        append_event(task_id, "command_cancel", {"command_id": payload["command_id"]})
    shutil.move(str(path), COMMANDS_PROCESSED_DIR / path.name)


def process_commands() -> None:
    for path in sorted(COMMANDS_PENDING_DIR.glob("*.yaml")):
        apply_command(path)


def process_tasks() -> None:
    for task_id in list_task_ids():
        init_task_runtime(task_id)
        state = load_state(task_id)
        if state.state in {"approved", "queued"}:
            launch_task(task_id)
            state = load_state(task_id)
            if state.state == "review_ready":
                send_text(f"[f713-control-plane] task `{task_id}` reached `review_ready`.")
            elif state.state == "blocked":
                send_text(f"[f713-control-plane] task `{task_id}` became `blocked`.")


def main() -> None:
    ensure_layout()
    settings = load_settings()
    ensure_repo()
    ensure_identity()
    while True:
        pull_fast_forward()
        process_commands()
        process_tasks()
        if commit_all("runtime: daemon sync"):
            if settings.git_push_enabled:
                push_with_app_auth()
        flush_pending()
        time.sleep(settings.daemon_poll_seconds)


if __name__ == "__main__":
    main()
