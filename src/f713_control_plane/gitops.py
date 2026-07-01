from __future__ import annotations

from pathlib import Path
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
    name = "chichaumiao-eng[bot]"
    email = "3037528+chichaumiao-eng[bot]@users.noreply.github.com"
    _run_git(["config", "user.name", name])
    _run_git(["config", "user.email", email])
    _run_git(["config", "pull.ff", "only"])
    _run_git(["config", "rebase.autoStash", "true"])
    _run_git(["config", "branch.autosetuprebase", "always"])
    _run_git(["config", f"branch.{settings.git_branch}.remote", settings.git_remote_name])
    _run_git(["config", f"branch.{settings.git_branch}.merge", f"refs/heads/{settings.git_branch}"])


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
    remote = _run_git(["remote"], check=True)
    if settings.git_remote_name not in remote.stdout.split():
        return
    _run_git(["fetch", settings.git_remote_name, settings.git_branch])
    _run_git(["pull", "--ff-only", settings.git_remote_name, settings.git_branch])


def push_with_app_auth() -> None:
    settings = load_settings()
    remote_names = _run_git(["remote"], check=True).stdout.split()
    if settings.git_remote_name not in remote_names:
        return
    remote_result = _run_git(["remote", "get-url", settings.git_remote_name], check=True)
    remote = remote_result.stdout.strip()
    token = get_installation_token()
    if remote.startswith("https://"):
        authed = remote.replace("https://", f"https://x-access-token:{token}@", 1)
    else:
        owner = settings.github_app_owner
        repo_name = ROOT.name
        authed = f"https://x-access-token:{token}@github.com/{owner}/{repo_name}.git"
    result = subprocess.run(
        ["git", "-C", str(ROOT), "push", authed, f"HEAD:{settings.git_branch}"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode == 0:
        return
    _run_git(["fetch", settings.git_remote_name, settings.git_branch])
    _run_git(["rebase", f"{settings.git_remote_name}/{settings.git_branch}"])
    refreshed = get_installation_token(force_refresh=True)
    retry_remote = authed.replace(token, refreshed)
    retry = subprocess.run(
        ["git", "-C", str(ROOT), "push", retry_remote, f"HEAD:{settings.git_branch}"],
        capture_output=True,
        text=True,
        check=False,
    )
    if retry.returncode != 0:
        stderr = retry.stderr.strip() or result.stderr.strip()
        raise RuntimeError(f"git push failed: {stderr}")
