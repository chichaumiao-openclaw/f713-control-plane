from __future__ import annotations

import argparse
from pathlib import Path
from string import Template
import uuid

from .config import TEMPLATES_DIR
from .gitops import commit_all, ensure_identity, ensure_repo, pull_fast_forward, push_with_app_auth
from .store import (
    COMMANDS_PENDING_DIR,
    append_event,
    ensure_layout,
    init_task_runtime,
    load_state,
    manifest_path,
    save_state,
    task_dir,
    write_yaml,
)


def render_template(name: str, values: dict[str, str]) -> str:
    path = TEMPLATES_DIR / f"{name}.yaml"
    payload = Template(path.read_text(encoding="utf-8")).substitute(values)
    return payload


def submit(args: argparse.Namespace) -> None:
    ensure_layout()
    ensure_repo()
    ensure_identity()
    pull_fast_forward()
    target = task_dir(args.task_id)
    if target.exists():
        raise SystemExit(f"Task already exists: {args.task_id}")
    target.mkdir(parents=True, exist_ok=False)
    manifest_text = render_template(
        args.template,
        {
            "task_id": args.task_id,
            "title": args.title,
            "entrypoint": args.entrypoint,
            "working_dir": args.working_dir,
            "created_by": args.created_by,
            "project_ref": args.project_ref,
            "launch_mode": args.mode,
            "prompt": args.prompt,
        },
    )
    manifest_path(args.task_id).write_text(manifest_text, encoding="utf-8")
    init_task_runtime(args.task_id)
    append_event(args.task_id, "task_submitted", {"created_by": args.created_by})
    commit_all(f"submit: {args.task_id}")
    push_with_app_auth()
    print(f"submitted {args.task_id}")


def status(args: argparse.Namespace) -> None:
    state = load_state(args.task_id)
    print(f"{args.task_id}: {state.state} ({state.last_worker_status}) retries={state.retries}")


def write_command(task_id: str, action: str, requested_by: str) -> None:
    ensure_layout()
    ensure_repo()
    ensure_identity()
    pull_fast_forward()
    command_id = str(uuid.uuid4())
    payload = {
        "schema_version": 1,
        "command_id": command_id,
        "task_id": task_id,
        "action": action,
        "requested_by": requested_by,
        "payload": {},
    }
    write_yaml(COMMANDS_PENDING_DIR / f"{command_id}.yaml", payload)
    commit_all(f"{action}: {task_id}")
    push_with_app_auth()
    print(f"{action} queued for {task_id}")


def resume(args: argparse.Namespace) -> None:
    write_command(args.task_id, "resume", args.requested_by)


def cancel(args: argparse.Namespace) -> None:
    write_command(args.task_id, "cancel", args.requested_by)


def install_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="f713ctl")
    subparsers = parser.add_subparsers(dest="command", required=True)

    submit_parser = subparsers.add_parser("submit")
    submit_parser.add_argument("--template", default="engineering_simple")
    submit_parser.add_argument("--task-id", required=True)
    submit_parser.add_argument("--title", required=True)
    submit_parser.add_argument("--entrypoint", default="")
    submit_parser.add_argument("--working-dir", default=".")
    submit_parser.add_argument("--created-by", default="chichau")
    submit_parser.add_argument("--project-ref", default="misc")
    submit_parser.add_argument("--mode", choices=["shell", "codex_exec"], default="shell")
    submit_parser.add_argument("--prompt", default="")
    submit_parser.set_defaults(func=submit)

    status_parser = subparsers.add_parser("status")
    status_parser.add_argument("--task-id", required=True)
    status_parser.set_defaults(func=status)

    resume_parser = subparsers.add_parser("resume")
    resume_parser.add_argument("--task-id", required=True)
    resume_parser.add_argument("--requested-by", default="chichau")
    resume_parser.set_defaults(func=resume)

    cancel_parser = subparsers.add_parser("cancel")
    cancel_parser.add_argument("--task-id", required=True)
    cancel_parser.add_argument("--requested-by", default="chichau")
    cancel_parser.set_defaults(func=cancel)

    return parser


def main() -> None:
    parser = install_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
