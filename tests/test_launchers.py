import os
import subprocess
import tomllib
from pathlib import Path

import pytest
from packaging.markers import default_environment
from packaging.requirements import Requirement

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("platform", ["win32", "linux", "darwin"])
def test_gpu_extra_does_not_install_cpu_and_gpu_paddle_together(platform: str) -> None:
    config = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    requirements = config["project"]["optional-dependencies"]["formula-gpu"]
    environment = {**default_environment(), "sys_platform": platform}
    runtimes = {
        req.name
        for item in requirements
        if (req := Requirement(item)).name in {"paddlepaddle", "paddlepaddle-gpu"}
        and (req.marker is None or req.marker.evaluate(environment))
    }
    assert runtimes == ({"paddlepaddle"} if platform == "darwin" else {"paddlepaddle-gpu"})


def test_windows_setup_defaults_to_formula_libraries_without_loading_models() -> None:
    script = (ROOT / "start-research.cmd").read_text(encoding="utf-8")
    defaults = script.split(":parse_arguments", 1)[0]
    assert 'set "INSTALL_FORMULA=1"' in defaults
    assert '"--without-formula"' in script
    assert '"--with-formula"' in script
    check = script.split("\n:formula_dependencies_available", 1)[1].split(
        "\n:install_project", 1
    )[0]
    assert "scripts\\setup_runtime.py" in check
    assert "FormulaRecognition(" not in check
    assert "--install %RUNTIME_OPTIONS%" in script
    assert "import_module('paddle')" not in script


def test_windows_checks_libraries_before_returning_to_existing_server() -> None:
    script = (ROOT / "start-research.cmd").read_text(encoding="utf-8")
    check_position = script.index("call :formula_dependencies_available")
    return_position = script.index('if "%SERVER_RUNNING%"=="1" (')
    assert check_position < return_position
    confirmation = script.split("\n:confirm_download", 1)[1]
    assert 'if "%SERVER_RUNNING%"=="1" (' in confirmation
    assert "Stop the running Econ Research server" in confirmation


def test_existing_server_offers_stop_restart_and_explicit_read_only_viewer() -> None:
    script = (ROOT / "start-research.cmd").read_text(encoding="utf-8")
    branch = script.split('if "%SERVER_RUNNING%"=="1" (', 1)[1].split("\n)\n", 1)[0]
    assert "goto :existing_server_menu" in branch
    assert "research serve" not in branch
    assert "taskkill" not in branch
    menu = script.split("\n:existing_server_menu", 1)[1].split("\n:find_conda", 1)[0]
    assert "choice /c RSLQ" in menu
    assert "goto :start_foreground" in menu
    assert "stop-server.ps1" in menu
    assert "watch-server-logs.ps1" in menu
    assert 'call "%~dp0start-research.cmd" --stop' in (
        ROOT / "stop-research.cmd"
    ).read_text()


@pytest.mark.skipif(os.name != "nt", reason="Exercises Windows PowerShell")
def test_log_viewer_reads_both_streams_without_modifying_files(tmp_path: Path) -> None:
    logs = tmp_path / "data"
    logs.mkdir()
    stdout = logs / "server-windows.stdout.log"
    stderr = logs / "server-windows.stderr.log"
    stdout.write_text("stdout progress\n", encoding="utf-8")
    stderr.write_text("stderr warning\n", encoding="utf-8")
    before = [(path.read_bytes(), path.stat().st_mtime_ns) for path in (stdout, stderr)]
    result = subprocess.run(
        [
            "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
            str(ROOT / "scripts" / "watch-server-logs.ps1"),
            "-ProjectDir", str(tmp_path), "-EncodingName", "utf-8", "-Once",
        ],
        capture_output=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr
    assert b"stdout progress" in result.stdout
    assert b"stderr warning" in result.stdout
    assert before == [(path.read_bytes(), path.stat().st_mtime_ns) for path in (stdout, stderr)]


@pytest.mark.skipif(os.name != "nt", reason="Exercises the native Windows command interpreter")
def test_windows_bootstrap_then_repeat_setup_without_reinstall(tmp_path: Path) -> None:
    project = tmp_path / "project's folder with spaces"
    project.mkdir()
    api = project / "src" / "econ_research" / "api.py"
    api.parent.mkdir(parents=True)
    api.write_text('WEB_UI_VERSION = "test"\n', encoding="utf-8")
    script = (ROOT / "start-research.cmd").read_text(encoding="utf-8")
    # Isolate the test from the real service: always simulate a free port.
    start = script.index("\n:check_existing_server\n")
    end = script.index("\n:editable_install_matches\n", start)
    script = script[:start] + "\n:check_existing_server\nexit /b 1\n" + script[end:]
    launcher = project / "start-research.cmd"
    launcher.write_text(script, encoding="utf-8")
    conda = project / "fake-conda.cmd"
    conda.write_text(
        '@echo off\n'
        'if "%~1"=="env" (\n'
        '  echo created>"%~dp0env-ready"\n'
        '  exit /b 0\n'
        ')\n'
        'if not exist "%~dp0env-ready" exit /b 1\n'
        'if "%~5"=="--version" exit /b 0\n'
        'if "%~7"=="--install" (\n'
        '  echo installed>>"%~dp0installed"\n'
        '  exit /b 0\n'
        ')\n'
        'if not exist "%~dp0installed" exit /b 1\n'
        'exit /b 0\n',
        encoding="utf-8",
    )
    env = {**os.environ, "CONDA_EXE": str(conda), "ECON_RESEARCH_NO_PAUSE": "1"}
    for _ in range(2):
        result = subprocess.run(
            ["cmd.exe", "/d", "/c", "start-research.cmd --setup-only --no-open"],
            cwd=project,
            env=env,
            input=b"Y\n",
            capture_output=True,
            timeout=30,
        )
        assert result.returncode == 0, (result.stdout, result.stderr)
        assert b"Setup and validation completed successfully" in result.stdout
    assert (project / "env-ready").exists()
    assert (project / "installed").read_text().splitlines() == ["installed"]


def test_mac_launcher_uses_shared_model_free_installer():
    script = (ROOT / "start-research.command").read_text(encoding="utf-8")
    assert "scripts/setup_runtime.py --install" in script
    assert "env create" in script
    assert "--setup-only" in script
    assert "2026-08-27-markdown-math-v1" not in script
