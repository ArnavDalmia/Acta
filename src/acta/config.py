"""Configuration loading for Acta.

Priority (highest wins): env vars > project config > user config > defaults.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomli as tomllib  # type: ignore[no-redef]
    except ImportError:
        tomllib = None  # type: ignore[assignment]


DEFAULT_DB_DIR = Path.home() / ".acta"
DEFAULT_DB_PATH = DEFAULT_DB_DIR / "acta.db"
DEFAULT_SERVER_HOST = "127.0.0.1"
DEFAULT_SERVER_PORT = 7432
DEFAULT_UI_PORT = 7433
DEFAULT_MODEL = "gpt-4.1-mini"
DEFAULT_PROVIDER = "openai"

# Default models per provider (used in docs/hints only)
PROVIDER_DEFAULT_MODELS = {
    "openai": "gpt-4.1-mini",
    "anthropic": "claude-haiku-3-5-20241022",
    "deepseek": "deepseek-chat",
    "ollama": "llama3.2",
}

PROJECT_CONFIG_DIR = ".acta"
PROJECT_CONFIG_FILE = "project.json"
USER_CONFIG_PATH = DEFAULT_DB_DIR / "config.toml"


@dataclass
class CoreConfig:
    db_path: Path = DEFAULT_DB_PATH


@dataclass
class ServerConfig:
    host: str = DEFAULT_SERVER_HOST
    port: int = DEFAULT_SERVER_PORT
    transport: str = "stdio"


@dataclass
class AgentConfig:
    enabled: bool = False
    provider: str = DEFAULT_PROVIDER
    model: str = DEFAULT_MODEL
    api_key: Optional[str] = None
    base_url: Optional[str] = None  # override for ollama host or deepseek-compatible endpoints


@dataclass
class UIConfig:
    enabled: bool = False
    port: int = DEFAULT_UI_PORT


@dataclass
class ActaConfig:
    core: CoreConfig = field(default_factory=CoreConfig)
    server: ServerConfig = field(default_factory=ServerConfig)
    agent: AgentConfig = field(default_factory=AgentConfig)
    ui: UIConfig = field(default_factory=UIConfig)


def _load_toml(path: Path) -> dict:
    if tomllib is None or not path.exists():
        return {}
    with open(path, "rb") as f:
        return tomllib.load(f)


def _apply_env(cfg: ActaConfig) -> None:
    """Override config values from environment variables."""
    if v := os.environ.get("ACTA_DB_PATH"):
        cfg.core.db_path = Path(v)

    if v := os.environ.get("ACTA_SERVER_HOST"):
        cfg.server.host = v
    if v := os.environ.get("ACTA_SERVER_PORT"):
        cfg.server.port = int(v)
    if v := os.environ.get("ACTA_SERVER_TRANSPORT"):
        cfg.server.transport = v

    if v := os.environ.get("ACTA_LLM_API_KEY"):
        cfg.agent.api_key = v
    if v := os.environ.get("ACTA_LLM_PROVIDER"):
        cfg.agent.provider = v
    if v := os.environ.get("ACTA_LLM_MODEL"):
        cfg.agent.model = v
    if v := os.environ.get("ACTA_LLM_BASE_URL"):
        cfg.agent.base_url = v


def _apply_toml(cfg: ActaConfig, data: dict) -> None:
    """Merge parsed TOML data into config."""
    if core := data.get("core"):
        if v := core.get("db_path"):
            cfg.core.db_path = Path(v).expanduser()

    if server := data.get("server"):
        if v := server.get("host"):
            cfg.server.host = v
        if v := server.get("port"):
            cfg.server.port = int(v)
        if v := server.get("transport"):
            cfg.server.transport = v

    if agent := data.get("agent"):
        if "enabled" in agent:
            cfg.agent.enabled = bool(agent["enabled"])
        if v := agent.get("provider"):
            cfg.agent.provider = v
        if v := agent.get("model"):
            cfg.agent.model = v
        if v := agent.get("api_key"):
            cfg.agent.api_key = v
        if v := agent.get("api_key_env"):
            cfg.agent.api_key = os.environ.get(v)
        if v := agent.get("base_url"):
            cfg.agent.base_url = v

    if ui := data.get("ui"):
        if "enabled" in ui:
            cfg.ui.enabled = bool(ui["enabled"])
        if v := ui.get("port"):
            cfg.ui.port = int(v)


def load_config(project_dir: Optional[Path] = None) -> ActaConfig:
    """Load configuration with proper precedence."""
    cfg = ActaConfig()

    user_data = _load_toml(USER_CONFIG_PATH)
    _apply_toml(cfg, user_data)

    if project_dir:
        project_config = project_dir / PROJECT_CONFIG_DIR / "config.toml"
        project_data = _load_toml(project_config)
        _apply_toml(cfg, project_data)

    _apply_env(cfg)

    return cfg
