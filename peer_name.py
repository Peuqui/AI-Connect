"""The peer name of a STDIO client: one rule for the client and the watcher."""

import os
import socket
import sys
from collections.abc import Mapping
from pathlib import Path

# The STDIO client records its name here, one file per session process (see
# session_pid), so the session's watcher can look it up by CLAUDE_PID on every
# operating system
SESSIONS_DIR = Path.home() / ".config" / "ai-connect" / "sessions"


def peer_name(environ: Mapping[str, str], cwd: Path) -> str:
    """AI_CONNECT_PEER_NAME if set, else "Host:Project".

    The project is CLAUDE_PROJECT_DIR when Claude Code sets it for its MCP
    servers, whatever directory it starts them in. Other harnesses start the
    STDIO client in the project itself, so there the working directory
    names it.
    """
    if "AI_CONNECT_PEER_NAME" in environ:
        return environ["AI_CONNECT_PEER_NAME"]
    project = Path(environ["CLAUDE_PROJECT_DIR"]) if "CLAUDE_PROJECT_DIR" in environ else cwd
    return f"{socket.gethostname()}:{project.name}"


def record_session_name(session_pid: int, name: str) -> Path:
    """Note which peer name the session with this process id uses."""
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    path = SESSIONS_DIR / str(session_pid)
    path.write_text(name)
    return path


def session_name(session_pid: str) -> str | None:
    """The peer name the session with this process id recorded, if any."""
    path = SESSIONS_DIR / session_pid
    return path.read_text() if path.exists() else None


def session_pid() -> int:
    """Process id of the session (Claude Code) that started this MCP client.

    That is the parent, except on Windows: there a venv's python.exe is a
    launcher that starts the real interpreter as its child, so when the
    parent is itself a python.exe, the session is the launcher's parent.
    (The launcher's __PYVENV_LAUNCHER__ is gone by the time Python runs.)
    """
    parent = os.getppid()
    if sys.platform == "win32":
        launcher_parent, exe = _windows_process(parent)
        if exe.lower() in ("python.exe", "pythonw.exe"):
            return launcher_parent
    return parent


if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    class _ProcessEntry(ctypes.Structure):
        # PROCESSENTRY32W from the Toolhelp API
        _fields_ = [
            ("dwSize", wintypes.DWORD),
            ("cntUsage", wintypes.DWORD),
            ("th32ProcessID", wintypes.DWORD),
            ("th32DefaultHeapID", ctypes.c_size_t),
            ("th32ModuleID", wintypes.DWORD),
            ("cntThreads", wintypes.DWORD),
            ("th32ParentProcessID", wintypes.DWORD),
            ("pcPriClassBase", ctypes.c_long),
            ("dwFlags", wintypes.DWORD),
            ("szExeFile", ctypes.c_wchar * 260),
        ]

    def _windows_process(pid: int) -> tuple[int, str]:
        """Parent process id and executable name of pid, from a Toolhelp snapshot."""
        kernel32 = ctypes.windll.kernel32
        kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
        snapshot = kernel32.CreateToolhelp32Snapshot(0x2, 0)  # TH32CS_SNAPPROCESS
        entry = _ProcessEntry()
        entry.dwSize = ctypes.sizeof(entry)
        try:
            found = kernel32.Process32FirstW(snapshot, ctypes.byref(entry))
            while found:
                if entry.th32ProcessID == pid:
                    return int(entry.th32ParentProcessID), entry.szExeFile
                found = kernel32.Process32NextW(snapshot, ctypes.byref(entry))
        finally:
            kernel32.CloseHandle(snapshot)
        raise LookupError(f"process {pid} not found")
