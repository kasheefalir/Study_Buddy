"""Register a user-local launcher without installing globally or using sudo."""
import os
from pathlib import Path
import shlex
import shutil
import sys


MARKER = "Study Buddy managed launcher v1"
PATH_MARKER = "# Study Buddy command path"


def launcher_text(root, python, windows=False):
    if any(char in str(value) for value in (root, python) for char in "\r\n"):
        raise ValueError("The project and Python paths must not contain newlines.")
    if windows:
        # Percent expansion happens even inside cmd.exe quotes.
        root, python = (str(value).replace("%", "%%") for value in (root, python))
        return (f"@echo off\nrem {MARKER}\nsetlocal DisableDelayedExpansion\n"
                f'cd /d "{root}" || exit /b 1\n'
                f'"{python}" -m app.cli %*\nexit /b %errorlevel%\n')
    return (f"#!/bin/sh\n# {MARKER}\n"
            f"cd {shlex.quote(str(root))} || exit 1\n"
            f"exec {shlex.quote(str(python))} -m app.cli \"$@\"\n")


def write_launcher(target, content):
    if target.is_symlink():
        raise ValueError(f"Refusing to replace a symbolic link: {target}")
    if target.exists() and MARKER not in target.read_text(encoding="utf-8"):
        raise ValueError(f"An unrelated command already exists at {target}; it was not changed.")
    existing = shutil.which("study")
    if existing and Path(existing).resolve() != target.resolve():
        raise ValueError(f"Another study command exists at {existing}; it was not changed.")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    if os.name != "nt":
        target.chmod(0o755)


def add_shell_path(profile, bin_dir):
    previous = profile.read_text(encoding="utf-8") if profile.exists() else ""
    line = f'export PATH="$PATH":{shlex.quote(str(bin_dir))}'
    if line in previous.splitlines():
        return
    profile.parent.mkdir(parents=True, exist_ok=True)
    with profile.open("a", encoding="utf-8") as handle:
        handle.write(f"\n{PATH_MARKER}\n{line}\n")


def add_windows_path(bin_dir, registry=None):
    if registry is None:
        import winreg as registry
    with registry.CreateKeyEx(registry.HKEY_CURRENT_USER, "Environment", 0,
                              registry.KEY_READ | registry.KEY_WRITE) as key:
        try:
            previous, value_type = registry.QueryValueEx(key, "Path")
        except FileNotFoundError:
            previous, value_type = "", registry.REG_EXPAND_SZ
        if value_type not in (registry.REG_SZ, registry.REG_EXPAND_SZ):
            raise ValueError("The existing Windows user Path is not a text value; it was not changed.")
        normalize = lambda path: os.path.expandvars(path.strip().strip('"')).rstrip("\\/").casefold()
        if normalize(str(bin_dir)) not in [normalize(part) for part in previous.split(";")]:
            updated = previous + (";" if previous and not previous.endswith(";") else "") + str(bin_dir)
            registry.SetValueEx(key, "Path", 0, value_type, updated)


def install(root=None, python=None, home=None):
    root = Path(root or Path(__file__).resolve().parents[1]).absolute()
    # Preserve a virtual environment's executable path rather than resolving its symlink.
    python = Path(python or sys.executable).absolute()
    home = Path(home or Path.home())
    if os.name == "nt":
        bin_dir = Path(os.environ.get("LOCALAPPDATA", home / "AppData" / "Local")) / "StudyBuddy" / "bin"
        target = bin_dir / "study.cmd"
        write_launcher(target, launcher_text(root, python, windows=True))
        add_windows_path(bin_dir)
        # Notify Explorer so newly opened terminals can inherit the new user PATH.
        import ctypes
        from ctypes import wintypes
        result = ctypes.c_size_t()
        notify = ctypes.windll.user32.SendMessageTimeoutW
        notify.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM,
                           wintypes.LPCWSTR, wintypes.UINT, wintypes.UINT,
                           ctypes.POINTER(ctypes.c_size_t)]
        notify.restype = wintypes.LPARAM
        notify(0xFFFF, 0x001A, 0, "Environment", 0x0002, 5000, ctypes.byref(result))
    else:
        shell = Path(os.environ.get("SHELL", "/bin/zsh" if sys.platform == "darwin" else "/bin/bash")).name
        if shell not in {"zsh", "bash"}:
            raise ValueError("Automatic command registration supports bash and zsh. Use the existing start script for this shell.")
        bin_dir = home / ".local" / "bin"
        target = bin_dir / "study"
        write_launcher(target, launcher_text(root, python))
        if shell == "zsh":
            add_shell_path(Path(os.environ.get("ZDOTDIR", home)) / ".zshrc", bin_dir)
        else:
            add_shell_path(home / ".bashrc", bin_dir)
            login_profile = next((home / name for name in (".bash_profile", ".bash_login", ".profile")
                                  if (home / name).exists()), home / ".bash_profile")
            add_shell_path(login_profile, bin_dir)
    return target


def main():
    try:
        target = install()
    except (OSError, ValueError) as exc:
        print(f"Could not register study buddy: {exc}", file=sys.stderr)
        return 1
    print(f"Installed command: {target}\nClose your terminal application and reopen it, then type: study buddy")
    print("Keep the project folder in place. If you move it, repeat setup and command registration.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
