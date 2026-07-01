from __future__ import annotations

from pathlib import Path
import os
import subprocess

from .config import load_settings
from .store import (
    append_event,
    artifacts_path,
    init_task_runtime,
    load_manifest,
    load_state,
    receipt_path,
    save_state,
    write_json,
)


def _run_shell(entrypoint: str, working_dir: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        entrypoint,
        shell=True,
        cwd=str(working_dir),
        capture_output=True,
        text=True,
    )


def _run_codex_exec(manifest: dict, working_dir: Path) -> subprocess.CompletedProcess[str]:
    settings = load_settings()
    prompt = str(manifest.get("launch", {}).get("prompt", "")).strip()
    if not prompt:
        raise RuntimeError("codex_exec launch requires launch.prompt")
    env = os.environ.copy()
    env["CODEX_HOME"] = settings.codex_home
    cmd = [
        settings.codex_bin,
        "exec",
        "--dangerously-bypass-approvals-and-sandbox",
        "--skip-git-repo-check",
        "--cd",
        str(working_dir),
        "-p",
        settings.codex_profile,
        "-m",
        settings.codex_provider_model,
        prompt,
    ]
    return subprocess.run(
        cmd,
        cwd=str(working_dir),
        capture_output=True,
        text=True,
        env=env,
    )


def launch_task(task_id: str) -> None:
    init_task_runtime(task_id)
    manifest = load_manifest(task_id)
    state = load_state(task_id)
    if state.state in {"running", "closed", "blocked", "cancelled"}:
        return
    launch = manifest.get("launch", {})
    launch_mode = str(launch.get("mode", "shell")).strip() or "shell"
    entrypoint = launch.get("entrypoint", "").strip()
    working_dir = Path(launch.get("working_dir", ".")).expanduser()
    state.state = "running"
    state.last_worker_status = "launched"
    save_state(state)
    append_event(task_id, "state_transition", {"state": "running"})

    if launch_mode == "shell" and not entrypoint:
        state.state = "blocked"
        state.last_worker_status = "missing_entrypoint"
        save_state(state)
        append_event(task_id, "blocked", {"reason": "missing entrypoint"})
        return

    try:
        if launch_mode == "shell":
            result = _run_shell(entrypoint, working_dir)
        elif launch_mode == "codex_exec":
            result = _run_codex_exec(manifest, working_dir)
        else:
            raise RuntimeError(f"Unsupported launch mode: {launch_mode}")
    except Exception as exc:
        state.state = "blocked"
        state.last_worker_status = "launch_exception"
        write_json(
            artifacts_path(task_id),
            {
                "artifacts": [
                    {
                        "type": "exception",
                        "preview": str(exc),
                    }
                ]
            },
        )
        from .store import blocker_path

        blocker_path(task_id).write_text(
            f"# Blocker\n\n- task_id: `{task_id}`\n- reason: `{str(exc)}`\n",
            encoding="utf-8",
        )
        append_event(task_id, "worker_failed", {"reason": str(exc)})
        save_state(state)
        return
    artifact_payload = {
        "artifacts": [
            {
                "type": "stdout",
                "preview": result.stdout[:500],
            },
            {
                "type": "stderr",
                "preview": result.stderr[:500],
            },
        ]
    }
    write_json(artifacts_path(task_id), artifact_payload)
    if result.returncode == 0:
        state.state = "review_ready"
        state.last_worker_status = "completed"
        state.last_progress_marker = "process_exit_0"
        receipt_path(task_id).write_text(
            f"# Receipt\n\n- task_id: `{task_id}`\n- status: `review_ready`\n- result: `process exited 0`\n",
            encoding="utf-8",
        )
        append_event(task_id, "worker_completed", {"returncode": 0})
    else:
        state.state = "blocked"
        state.last_worker_status = f"failed_{result.returncode}"
        receipt_path(task_id).write_text("", encoding="utf-8")
        from .store import blocker_path

        blocker_path(task_id).write_text(
            f"# Blocker\n\n- task_id: `{task_id}`\n- returncode: `{result.returncode}`\n- reason: `worker failed`\n",
            encoding="utf-8",
        )
        append_event(task_id, "worker_failed", {"returncode": result.returncode})
    save_state(state)
