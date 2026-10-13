import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from app import cli, install_command as installer


@pytest.mark.skipif(os.name == "nt", reason="POSIX shell profiles")
def test_installer_is_repeatable_and_preserves_profile(tmp_path, monkeypatch):
    monkeypatch.setenv("SHELL", "/bin/zsh")
    monkeypatch.delenv("ZDOTDIR", raising=False)
    monkeypatch.setattr(shutil, "which", lambda name: None)
    profile = tmp_path / ".zshrc"
    profile.write_text("# My settings\nexport EXAMPLE=1\n")
    root = tmp_path / "Study Buddy"
    first = installer.install(root=root, home=tmp_path)
    installer.install(root=root, home=tmp_path)
    assert profile.read_text().startswith("# My settings\nexport EXAMPLE=1\n")
    assert profile.read_text().count(installer.PATH_MARKER) == 1
    assert str(root) in first.read_text()
    assert os.access(first, os.X_OK)


@pytest.mark.skipif(os.name == "nt", reason="POSIX launcher integration")
def test_command_runs_from_another_directory_with_quoted_paths(tmp_path, monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda name: None)
    root = tmp_path / "Study Buddy's files"
    app = root / "app"
    app.mkdir(parents=True)
    (app / "__init__.py").write_text("")
    shutil.copyfile(Path(cli.__file__), app / "cli.py")
    (app / "launch.py").write_text("import os, sys\ndef main():\n print(os.getcwd())\n print(sys.argv[1:])\n return 0\n")
    executable = tmp_path / "bin" / "study"
    installer.write_launcher(executable, installer.launcher_text(root, sys.executable))
    environment = dict(os.environ, PATH=str(executable.parent) + os.pathsep + os.environ.get("PATH", ""))
    result = subprocess.run(["study", "buddy", "--port", "8123"], cwd=tmp_path,
                            env=environment, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert str(root) in result.stdout
    assert "['--port', '8123']" in result.stdout
    result = subprocess.run([str(executable), "other"], cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode == 2
    assert "Usage: study buddy" in result.stderr


def test_refuses_unrelated_command(tmp_path, monkeypatch):
    target = tmp_path / "study"
    target.write_text("some other program")
    with pytest.raises(ValueError, match="unrelated"):
        installer.write_launcher(target, "replacement")
    assert target.read_text() == "some other program"
    monkeypatch.setattr(shutil, "which", lambda name: "/other/bin/study")
    with pytest.raises(ValueError, match="Another study"):
        installer.write_launcher(tmp_path / "new" / "study", "replacement")


@pytest.mark.skipif(os.name == "nt", reason="POSIX virtual environment symlink")
def test_preserves_venv_interpreter_path(tmp_path, monkeypatch):
    monkeypatch.setenv("SHELL", "/bin/bash")
    monkeypatch.setattr(shutil, "which", lambda name: None)
    python = tmp_path / ".venv" / "bin" / "python"
    python.parent.mkdir(parents=True)
    python.symlink_to(sys.executable)
    target = installer.install(root=tmp_path, python=python, home=tmp_path)
    assert str(python) in target.read_text()
    assert (tmp_path / ".bashrc").exists()
    assert (tmp_path / ".bash_profile").exists()


def test_windows_wrapper_quotes_paths_and_forwards_arguments():
    text = installer.launcher_text(r"C:\Study Buddy\100% ready!", r"C:\Study Buddy\.venv\Scripts\python.exe", windows=True)
    assert 'cd /d "C:\\Study Buddy\\100%% ready!" || exit /b 1' in text
    assert '"C:\\Study Buddy\\.venv\\Scripts\\python.exe" -m app.cli %*' in text
    assert "DisableDelayedExpansion" in text


def test_windows_path_preserved_and_not_duplicated():
    class Registry:
        HKEY_CURRENT_USER = KEY_READ = KEY_WRITE = REG_EXPAND_SZ = 1
        REG_SZ = 2
        value = (r"%USERPROFILE%\Tools;C:\Existing", 1)
        writes = 0

        def CreateKeyEx(self, *args):
            return self

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def QueryValueEx(self, *args):
            return self.value

        def SetValueEx(self, key, name, reserved, kind, value):
            self.value = (value, kind)
            self.writes += 1

    registry = Registry()
    installer.add_windows_path(r"C:\StudyBuddy\bin", registry)
    installer.add_windows_path(r"c:\studybuddy\bin", registry)
    assert registry.value == (r"%USERPROFILE%\Tools;C:\Existing;C:\StudyBuddy\bin", 1)
    assert registry.writes == 1
