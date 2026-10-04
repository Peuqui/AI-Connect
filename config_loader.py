"""Reads the AI-Connect config for the Bridge Server and both MCP clients."""

from pathlib import Path

import yaml

CONFIG_PATH = Path.home() / ".config" / "ai-connect" / "config.yaml"


def load_config() -> dict:
    """Load ~/.config/ai-connect/config.yaml.

    No defaults: without a config the services would silently talk to
    some built-in address. Missing file or missing keys stop the start
    with a message instead.
    """
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(
            f"AI-Connect config not found: {CONFIG_PATH}\n"
            f"Run ./install.sh or create it from config.yaml.example."
        )
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


# Listening on these means "on every address of this machine"; as a target
# they mean this machine. Linux accepts 0.0.0.0 as a target, Windows refuses
# it (WinError 1214), so clients on the Bridge machine connect to loopback.
_LISTEN_ALL_TO_LOOPBACK = {"0.0.0.0": "127.0.0.1", "::": "::1"}


def bridge_target(host: str) -> str:
    """The address a client connects to for bridge.host."""
    return _LISTEN_ALL_TO_LOOPBACK.get(host, host)
