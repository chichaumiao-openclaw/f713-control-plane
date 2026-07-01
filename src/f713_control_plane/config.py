from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os


ROOT = Path(__file__).resolve().parents[2]
TASKS_DIR = ROOT / "tasks"
COMMANDS_PENDING_DIR = ROOT / "commands" / "pending"
COMMANDS_PROCESSED_DIR = ROOT / "commands" / "processed"
TEMPLATES_DIR = ROOT / "templates"
RUNTIME_DIR = ROOT / "runtime"
LOGS_DIR = RUNTIME_DIR / "logs"
PENDING_NOTIFICATIONS = RUNTIME_DIR / "pending_notifications.json"
ENV_PATH = Path.home() / ".config" / "f713-control-plane" / ".env"
CODEX_HOME = Path.home() / ".codex"


@dataclass(frozen=True)
class Settings:
    daemon_poll_seconds: int = 60
    hermes_poll_seconds: int = 300
    feishu_enabled: bool = False
    git_push_enabled: bool = False
    git_branch: str = "main"
    git_remote_name: str = "origin"
    github_app_id: str = ""
    github_app_installation_id: str = ""
    github_app_owner: str = ""
    github_app_pem_path: str = ""
    codex_bin: str = "codex"
    codex_profile: str = "agnes"
    codex_provider_base_url: str = "https://apihub.agnes-ai.com/v1"
    codex_provider_model: str = "agnes-2.0-flash"
    codex_home: str = str(CODEX_HOME)


def load_dotenv(path: Path = ENV_PATH) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def load_settings() -> Settings:
    load_dotenv()
    return Settings(
        daemon_poll_seconds=int(os.environ.get("F713_CONTROL_DAEMON_POLL_SECONDS", "60")),
        hermes_poll_seconds=int(os.environ.get("F713_CONTROL_HERMES_POLL_SECONDS", "300")),
        feishu_enabled=os.environ.get("F713_CONTROL_FEISHU_ENABLED", "0") == "1",
        git_push_enabled=os.environ.get("F713_CONTROL_GIT_PUSH", "0") == "1",
        git_branch=os.environ.get("F713_CONTROL_GIT_BRANCH", "main"),
        git_remote_name=os.environ.get("F713_CONTROL_GIT_REMOTE", "origin"),
        github_app_id=os.environ.get("GITHUB_APP_ID", "").strip(),
        github_app_installation_id=os.environ.get("GITHUB_APP_INSTALLATION_ID", "").strip(),
        github_app_owner=os.environ.get("GITHUB_APP_OWNER", "").strip(),
        github_app_pem_path=os.environ.get("GITHUB_APP_PEM_PATH", "").strip(),
        codex_bin=os.environ.get("F713_CONTROL_CODEX_BIN", "codex").strip() or "codex",
        codex_profile=os.environ.get("F713_CONTROL_CODEX_PROFILE", "agnes").strip() or "agnes",
        codex_provider_base_url=os.environ.get("F713_CONTROL_CODEX_BASE_URL", "https://apihub.agnes-ai.com/v1").strip(),
        codex_provider_model=os.environ.get("F713_CONTROL_CODEX_MODEL", "agnes-2.0-flash").strip(),
        codex_home=os.environ.get("CODEX_HOME", str(CODEX_HOME)).strip() or str(CODEX_HOME),
    )
