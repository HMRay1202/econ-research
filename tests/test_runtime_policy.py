import importlib.util
import sys
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "runtime_policy", Path(__file__).resolve().parents[1] / "scripts/runtime_policy.py"
)
policy = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = policy
SPEC.loader.exec_module(policy)


@pytest.mark.parametrize(
    ("system", "machine", "driver", "capability", "profile"),
    [
        ("Windows", "AMD64", "596.49", "12.0", "cuda13"),
        ("Windows", "AMD64", "572.0", "8.6", "cuda12"),
        ("Windows", "AMD64", "572.0", "12.0", "cpu"),
        ("Windows", "AMD64", "596.49", "6.1", "cpu"),
        ("Windows", "AMD64", "", "", "cpu"),
        ("Windows", "AMD64", "596.49", "3.5", "cpu"),
        ("Windows", "ARM64", "596.49", "12.0", "cpu"),
        ("Darwin", "arm64", "", "", "mac"),
        ("Darwin", "x86_64", "", "", "mac"),
        ("Linux", "x86_64", "596.49", "8.0", "cuda13"),
    ],
)
def test_runtime_selection(system, machine, driver, capability, profile):
    assert policy.select_runtime(system, machine, driver, capability).profile == profile


def test_detection_failure_is_cpu(monkeypatch):
    monkeypatch.setattr(policy.platform, "system", lambda: "Windows")
    monkeypatch.setattr(policy.platform, "machine", lambda: "AMD64")

    def missing(*args, **kwargs):
        raise FileNotFoundError("nvidia-smi")

    monkeypatch.setattr(policy.subprocess, "run", missing)
    assert policy.detect_runtime().profile == "cpu"
