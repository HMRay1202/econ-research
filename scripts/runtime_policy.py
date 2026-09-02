"""Standard-library-only hardware selection; importing this module installs nothing."""

from __future__ import annotations

import platform
import subprocess
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class RuntimePlan:
    profile: str
    torch_index: str
    paddle_index: str
    torch_version: str
    torchvision_version: str
    reason: str


def select_runtime(system: str, machine: str, driver: str = "", capability: str = ""):
    """Only enable CUDA for a supported driver *and* GPU, not merely an installed toolkit."""
    cpu = RuntimePlan(
        "cpu", "https://download.pytorch.org/whl/cpu",
        "https://www.paddlepaddle.org.cn/packages/stable/cpu/", "2.9.1", "0.24.1",
        "No supported NVIDIA GPU/driver; using CPU runtimes.",
    )
    if system == "Darwin":
        return RuntimePlan(
            "mac", "https://pypi.org/simple", cpu.paddle_index, "", "",
            "macOS: native PyTorch (MPS when available); Paddle uses CPU.",
        )
    if system not in {"Windows", "Linux"} or machine.lower() not in {"amd64", "x86_64"}:
        return cpu
    try:
        driver_parts = tuple(int(part) for part in driver.split(".")[:2])
        cc = float(capability)
    except ValueError:
        return cpu
    if driver_parts >= (580, 0) and 7.5 <= cc < 13:
        return RuntimePlan(
            "cuda13", "https://download.pytorch.org/whl/cu130",
            "https://www.paddlepaddle.org.cn/packages/stable/cu130/", "2.9.1", "0.24.1",
            "Supported NVIDIA GPU and CUDA 13 driver detected.",
        )
    if driver_parts >= (560, 76) and 7.5 <= cc < 10:
        return RuntimePlan(
            "cuda12", "https://download.pytorch.org/whl/cu126",
            "https://www.paddlepaddle.org.cn/packages/stable/cu126/", "2.6.0", "0.21.0",
            "Supported pre-Blackwell NVIDIA GPU; using CUDA 12.6 runtimes.",
        )
    return RuntimePlan(**{**asdict(cpu), "reason": (
        "GPU/driver is outside the supported CUDA profiles. CPU selected; "
        "update the NVIDIA driver for newer GPUs."
    )})


def detect_runtime() -> RuntimePlan:
    system, machine = platform.system(), platform.machine()
    if system == "Darwin":
        return select_runtime(system, machine)
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=driver_version,compute_cap", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=15, check=True,
        )
        # The application's default is device 0. Do not select a different GPU silently.
        driver, capability = result.stdout.splitlines()[0].split(",", 1)
        return select_runtime(system, machine, driver.strip(), capability.strip())
    except (OSError, subprocess.SubprocessError, ValueError, IndexError):
        return select_runtime(system, machine)


if __name__ == "__main__":
    import json

    print(json.dumps(asdict(detect_runtime()), indent=2))
