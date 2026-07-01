from __future__ import annotations

from pathlib import Path
import os
import subprocess

from .config import ROOT, load_settings
from .github_auth import get_installation_token


def _run_git(args: list[str], *, env: dict[str, str] | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(ROOT), *args],
        capture_output=True,
        text=True,
        env=env,
        check=check,
    )


def ensure_repo() -> None:
    if not (ROOT / ".git").exists():
        raise RuntimeError(f"{ROOT} is not a git repository")


def ensure_identity() -> None:
    settings = load_settings()
    name = os.environ.get("GIT_AUTHOR_NAME", "chichaumiao-eng[bot]")
    email = os.environ.get("GIT_AUTHOR_EMAIL", "3037528+chichaumiao-eng[bot]@users.noreply.github.com")
    _run_git(["config", "user.name", name])
    _run_git(["config", "user.email", email])
    _run_git(["config", "pull.ff", "only"])
    _run_git(["config", "rebase.autoStash", "true"])
    _run_git(["config", "branch.autosetuprebase", "always"])
    _run_git(["config", f"branch.{settings.git_branch}.remote", settings.git_remote_name])
    _run_git(["config", f"branch.{settings.git_branch}.merge", f"refs/heads/{settings.git_branch}"])


def _auth_env() -> dict[str, str]:
    token = get_installation_token()
    askpass_script = 'case "$1" in *Username*) echo "x-access-token" ;; *Password*) echo "$GITHUB_TOKEN" ;; *) echo "" ;; esac'
    env = os.environ.copy()
    env["GITHUB_TOKEN"] = token
    env["GIT_ASKPASS"] = "/bin/sh"
    env["SSH_ASKPASS"] = "/bin/sh"
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["F713_GIT_ASKPASS_SCRIPT"] = askpass_script
    return env


def has_changes() -> bool:
    result = _run_git(["status", "--porcelain"], check=True)
    return bool(result.stdout.strip())


def current_branch() -> str:
    result = _run_git(["rev-parse", "--abbrev-ref", "HEAD"], check=True)
    return result.stdout.strip()


def commit_all(message: str) -> bool:
    _run_git(["add", "-A"])
    if not has_changes():
        return False
    _run_git(["commit", "-m", message])
    return True


def pull_fast_forward() -> None:
    settings = load_settings()
    _run_git(["fetch", settings.git_remote_name, settings.git_branch])
    _run_git(["pull", "--ff-only", settings.git_remote_name, settings.git_branch])


def push_with_app_auth() -> None:
    settings = load_settings()
    env = _auth_env()
    remote_result = _run_git(["remote", "get-url", settings.git_remote_name], check=True)
    remote = remote_result.stdout.strip()
    if remote.startswith("https://"):
        authed = remote.replace("https://", f"https://x-access-token:{env['GITHUB_TOKEN']}@", 1)
    else:
        owner = settings.github_app_owner
        repo_name = ROOT.name
        authed = f"https://x-access-token:{env['GITHUB_TOKEN']}@github.com/{owner}/{repo_name}.git"
    result = subprocess.run(
        ["git", "-C", str(ROOT), "push", authed, f"HEAD:{settings.git_branch}"],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    if result.returncode == 0:
        return
    _run_git(["fetch", settings.git_remote_name, settings.git_branch])
    _run_git(["rebase", f"{settings.git_remote_name}/{settings.git_branch}"])
    env = _auth_env()
    retry_remote = authed.replace(env.get("GITHUB_TOKEN", ""), get_installation_token(force_refresh=True))
    retry = subprocess.run(
        ["git", "-C", str(ROOT), "push", retry_remote, f"HEAD:{settings.git_branch}"],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    if retry.returncode != 0:
        stderr = retry.stderr.strip() or result.stderr.strip()
        raise RuntimeError(f"git push failed: {stderr}")

