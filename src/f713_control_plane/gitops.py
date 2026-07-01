from __future__ import annotations

from pathlib import Path
import time
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


def _remote_names() -> list[str]:
    return _run_git(["remote"], check=True).stdout.split()


def _authenticated_remote_url() -> str:
    settings = load_settings()
    token = get_installation_token()
    if settings.git_remote_name in _remote_names():
        remote = _run_git(["remote", "get-url", settings.git_remote_name], check=True).stdout.strip()
        if remote.startswith("https://"):
            return remote.replace("https://", f"https://x-access-token:{token}@", 1)
    owner = settings.github_app_owner
    repo_name = ROOT.name
    return f"https://x-access-token:{token}@github.com/{owner}/{repo_name}.git"


def ensure_repo() -> None:
    if not (ROOT / ".git").exists():
        raise RuntimeError(f"{ROOT} is not a git repository")


def _git_config_get(key: str) -> str:
    result = _run_git(["config", "--get", key], check=False)
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def _git_config_set(key: str, value: str, retries: int = 3, sleep_seconds: float = 0.5) -> None:
    current = _git_config_get(key)
    if current == value:
        return
    last_error = ""
    for attempt in range(retries):
        result = _run_git(["config", key, value], check=False)
        if result.returncode == 0:
            return
        last_error = result.stderr.strip() or result.stdout.strip() or f"git config {key} failed"
        if "could not lock config file" not in last_error.lower() or attempt == retries - 1:
            raise RuntimeError(last_error)
        time.sleep(sleep_seconds)
    raise RuntimeError(last_error)


def ensure_identity() -> None:
    settings = load_settings()
    name = "chichaumiao-eng[bot]"
    email = "3037528+chichaumiao-eng[bot]@users.noreply.github.com"
    _git_config_set("user.name", name)
    _git_config_set("user.email", email)
    _git_config_set("pull.ff", "only")
    _git_config_set("rebase.autoStash", "true")
    _git_config_set("branch.autosetuprebase", "always")
    _git_config_set(f"branch.{settings.git_branch}.remote", settings.git_remote_name)
    _git_config_set(f"branch.{settings.git_branch}.merge", f"refs/heads/{settings.git_branch}")


def has_changes() -> bool:
    result = _run_git(["status", "--porcelain"], check=True)
    return bool(result.stdout.strip())


def has_uncommitted_changes() -> bool:
    return has_changes()


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
    if settings.git_remote_name not in _remote_names():
        return
    if has_uncommitted_changes():
        return
    authed_remote = _authenticated_remote_url()
    fetch = _run_git(["fetch", authed_remote, settings.git_branch], check=False)
    if fetch.returncode != 0:
        return
    _run_git(["reset", "--hard", "FETCH_HEAD"])


def push_with_app_auth() -> None:
    settings = load_settings()
    remote_names = _remote_names()
    if settings.git_remote_name not in remote_names:
        return
    authed = _authenticated_remote_url()
    result = subprocess.run(
        ["git", "-C", str(ROOT), "push", authed, f"HEAD:{settings.git_branch}"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode == 0:
        return
    retry_remote = _authenticated_remote_url()
    _run_git(["fetch", retry_remote, settings.git_branch])
    _run_git(["rebase", "FETCH_HEAD"])
    retry = subprocess.run(
        ["git", "-C", str(ROOT), "push", retry_remote, f"HEAD:{settings.git_branch}"],
        capture_output=True,
        text=True,
        check=False,
    )
    if retry.returncode != 0:
        stderr = retry.stderr.strip() or result.stderr.strip()
        raise RuntimeError(f"git push failed: {stderr}")
