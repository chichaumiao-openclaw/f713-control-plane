from __future__ import annotations

import time

from .config import load_settings
from .notifier import send_text
from .store import append_event, list_task_ids, load_manifest, load_state, save_state


def should_watch(manifest: dict, state_value: str) -> bool:
    watchdog = manifest.get("watchdog", {})
    return (
        manifest.get("task_class") == "engineering_simple"
        and watchdog.get("enabled", False)
        and state_value in {"running", "review_ready"}
    )


def progress_marker(manifest: dict, state) -> str:
    completion_checks = manifest.get("completion_checks", [])
    expected_outputs = manifest.get("expected_outputs", [])
    return f"{state.last_worker_status}|checks={len(completion_checks)}|outputs={len(expected_outputs)}"


def inspect_task(task_id: str) -> None:
    manifest = load_manifest(task_id)
    state = load_state(task_id)
    if not should_watch(manifest, state.state):
        return

    marker = progress_marker(manifest, state)
    if state.state == "review_ready":
        if marker == state.last_progress_marker:
            state.continuation_count += 1
        else:
            state.last_progress_marker = marker
            state.continuation_count = 0

        max_retries = int(manifest.get("watchdog", {}).get("max_retries", 3))
        stall_cutoff = int(manifest.get("watchdog", {}).get("stall_cutoff", 2))

        if state.continuation_count >= stall_cutoff:
            state.retries += 1
            append_event(task_id, "hermes_continue", {"retry": state.retries})
            if state.retries > max_retries:
                state.state = "blocked"
                state.last_worker_status = "hermes_max_retries"
                append_event(task_id, "hermes_blocked", {"reason": "max retries exceeded"})
                send_text(f"[hermes] task `{task_id}` blocked after repeated incomplete checks.")
            else:
                state.state = "approved"
                state.last_worker_status = "hermes_requested_continue"
                send_text(f"[hermes] task `{task_id}` still incomplete, requeued for continuation.")
        save_state(state)


def main() -> None:
    settings = load_settings()
    while True:
        for task_id in list_task_ids():
            inspect_task(task_id)
        time.sleep(settings.hermes_poll_seconds)


if __name__ == "__main__":
    main()
