from pathlib import Path

LAUNCHER = Path(__file__).parents[1] / "start-research.cmd"


def test_windows_launcher_streams_long_running_command_output() -> None:
    script = LAUNCHER.read_text(encoding="utf-8")

    assert 'run --no-capture-output -n econ-research python "%PROJECT_DIR%' in script
    assert '\\scripts\\setup_runtime.py" --install' in script
    assert '"%SERVER_PYTHON%" -u -m econ_research.cli serve' in script


def test_windows_launcher_keeps_formula_dependencies_optional() -> None:
    script = LAUNCHER.read_text(encoding="utf-8")

    assert 'set "INSTALL_FORMULA=0"' in script
    assert 'if /I "%~1"=="--with-formula"' in script
    assert 'set "RUNTIME_OPTIONS=--without-formula"' in script


def test_windows_launcher_reads_ui_version_from_source() -> None:
    script = LAUNCHER.read_text(encoding="utf-8")

    assert "WEB_UI_VERSION =" in script
    assert "2026-08-27-markdown-math-v1" not in script
