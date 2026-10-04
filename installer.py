"""The platform-independent steps of the AI-Connect installation.

install.sh (Linux) and install.ps1 (Windows) create the venv, install the
dependencies and set up the services. Everything else happens here, run
with the venv's Python, so it is written once for both:

    installer.py config --server   # Bridge machine: write the config, generate the token
    installer.py config --client   # every other machine: write the config, ask for the token
    installer.py claude            # register the MCP server and the plugin with Claude Code
    installer.py unregister        # remove both from Claude Code again
"""

import argparse
import json
import os
import secrets
import shutil
import socket
import subprocess
import sys
from pathlib import Path

import yaml

from config_loader import CONFIG_PATH

REPO = Path(__file__).resolve().parent
CONFIG_EXAMPLE = REPO / "config.yaml.example"
MCP_SERVER = "ai-connect"
MARKETPLACE = "ai-connect"
PLUGIN = "ai-connect@ai-connect"
# What `claude mcp remove` says when there is nothing to remove
NOT_REGISTERED = "No MCP server named"


def _dotted_keys(tree: dict, prefix: str = "") -> set[str]:
    keys = set()
    for key, value in tree.items():
        path = f"{prefix}{key}"
        keys |= _dotted_keys(value, f"{path}.") if isinstance(value, dict) else {path}
    return keys


def _example() -> dict:
    with open(CONFIG_EXAMPLE) as f:
        return yaml.safe_load(f)


def check_config() -> None:
    """Stop with a list of the keys config.yaml lacks compared to the template."""
    with open(CONFIG_PATH) as f:
        missing = _dotted_keys(_example()) - _dotted_keys(yaml.safe_load(f))
    if missing:
        sys.exit(
            f"{CONFIG_PATH} lacks: {', '.join(sorted(missing))}\n"
            f"Add them as in {CONFIG_EXAMPLE} and run the installer again."
        )


def _ask(question: str, default: str | None = None) -> str:
    answer = input(f"  {question}" + (f" [{default}]" if default else "") + ": ").strip()
    if answer:
        return answer
    if default is None:
        sys.exit(f"No answer to '{question}'. Aborted.")
    return default


def write_config(server: bool) -> None:
    """Write config.yaml from the template; an existing one is only checked."""
    if CONFIG_PATH.exists():
        check_config()
        print(f"  Config kept: {CONFIG_PATH}")
        return

    config = _example()
    # Name of this machine's HTTP/SSE server; Claude Code sessions name
    # themselves Host:Project
    config["peer"]["name"] = _ask("Peer name of this machine's HTTP/SSE server", socket.gethostname())
    if server:
        # On the Bridge machine bridge.host is both the listen address and
        # the address the local clients connect to; 0.0.0.0 serves both,
        # 127.0.0.1 would lock out every other machine
        config["bridge"]["host"] = _ask("Bridge listen address", "0.0.0.0")
        config["bridge"]["token"] = secrets.token_hex(32)
        print(f"  Bridge token, enter it on every client machine: {config['bridge']['token']}")
    else:
        config["bridge"]["host"] = _ask("IP or hostname of the Bridge machine")
        config["bridge"]["token"] = _ask("Bridge token (bridge.token in the Bridge machine's config)")

    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        yaml.safe_dump(config, f, sort_keys=False)
    # The token is a secret; on Windows this only clears the read-only flag
    CONFIG_PATH.chmod(0o600)
    print(f"  Config written: {CONFIG_PATH}")


def _find_claude() -> str | None:
    """Claude Code's CLI: from PATH, else where its native installer puts it.

    On Windows the native installer does not add ~/.local/bin to PATH.
    """
    found = shutil.which("claude")
    if found:
        return found
    native = Path.home() / ".local" / "bin" / ("claude.exe" if sys.platform == "win32" else "claude")
    if native.exists():
        print(f"  {native} is not in PATH; using it directly. Add {native.parent} to PATH for the terminal.")
        return str(native)
    return None


def _claude(claude: str, *args: str) -> subprocess.CompletedProcess:
    # check=False: the callers judge the return code themselves (see _check)
    return subprocess.run([claude, *args], capture_output=True, text=True, check=False)


def _check(result: subprocess.CompletedProcess, what: str) -> None:
    if result.returncode != 0:
        sys.exit(f"{what} failed:\n{result.stdout}{result.stderr}")


def register_claude() -> None:
    """Register the MCP server (with this venv's Python) and the plugin with Claude Code."""
    claude = _find_claude()
    if claude is None:
        print(
            "  Claude Code not found in PATH. Once it is installed, run:\n"
            f'    "{os.path.abspath(sys.executable)}" "{REPO / "installer.py"}" claude'
        )
        return

    # Replace an existing registration, so a moved repository or a new venv
    # takes effect
    removed = _claude(claude, "mcp", "remove", "-s", "user", MCP_SERVER)
    if removed.returncode != 0 and NOT_REGISTERED not in removed.stdout + removed.stderr:
        _check(removed, "claude mcp remove")
    # abspath, not resolve(): resolving follows the venv's symlink to the system Python
    python = os.path.abspath(sys.executable)
    _check(
        _claude(claude, "mcp", "add", "-s", "user", MCP_SERVER, "--", python, str(REPO / "client" / "server.py")),
        "claude mcp add",
    )
    print(f"  MCP server '{MCP_SERVER}' registered: {python}")

    marketplaces = {m["name"] for m in json.loads(_claude(claude, "plugin", "marketplace", "list", "--json").stdout)}
    if MARKETPLACE in marketplaces:
        _check(_claude(claude, "plugin", "marketplace", "update", MARKETPLACE), "claude plugin marketplace update")
    else:
        _check(_claude(claude, "plugin", "marketplace", "add", str(REPO)), "claude plugin marketplace add")

    plugins = {p["id"] for p in json.loads(_claude(claude, "plugin", "list", "--json").stdout)}
    if PLUGIN in plugins:
        _check(_claude(claude, "plugin", "update", PLUGIN), "claude plugin update")
    else:
        _check(_claude(claude, "plugin", "install", PLUGIN), "claude plugin install")
    print(f"  Plugin {PLUGIN} installed (state hooks, /ai-connect:consult); new sessions pick it up")


def unregister_claude() -> None:
    """Remove the MCP server, the plugin and the marketplace from Claude Code."""
    claude = _find_claude()
    if claude is None:
        print("  Claude Code not found in PATH, nothing to remove there")
        return
    removed = _claude(claude, "mcp", "remove", "-s", "user", MCP_SERVER)
    if removed.returncode != 0 and NOT_REGISTERED not in removed.stdout + removed.stderr:
        _check(removed, "claude mcp remove")
    if PLUGIN in {p["id"] for p in json.loads(_claude(claude, "plugin", "list", "--json").stdout)}:
        _check(_claude(claude, "plugin", "uninstall", PLUGIN), "claude plugin uninstall")
    if MARKETPLACE in {m["name"] for m in json.loads(_claude(claude, "plugin", "marketplace", "list", "--json").stdout)}:
        _check(_claude(claude, "plugin", "marketplace", "remove", MARKETPLACE), "claude plugin marketplace remove")
    print("  AI-Connect removed from Claude Code")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    steps = parser.add_subparsers(dest="step", required=True)
    config = steps.add_parser("config", help="write or check ~/.config/ai-connect/config.yaml")
    mode = config.add_mutually_exclusive_group(required=True)
    mode.add_argument("--server", action="store_true", help="Bridge machine: generate the token")
    mode.add_argument("--client", action="store_true", help="other machines: ask for the token")
    steps.add_parser("claude", help="register the MCP server and the plugin with Claude Code")
    steps.add_parser("unregister", help="remove the MCP server and the plugin from Claude Code")
    args = parser.parse_args()

    if args.step == "config":
        write_config(server=args.server)
    elif args.step == "claude":
        register_claude()
    else:
        unregister_claude()


if __name__ == "__main__":
    main()
