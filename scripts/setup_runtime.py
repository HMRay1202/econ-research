"""Bootstrap libraries only. Models are loaded exclusively by actual recognition."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
import platform
import subprocess
import sys
import urllib.request
from dataclasses import asdict
from pathlib import Path

from runtime_policy import detect_runtime

ROOT = Path(__file__).resolve().parents[1]
WORKER_SCRIPT = ROOT / "src/econ_research/parsing/paddle_worker.py"
WORKER_ROOT = Path(sys.prefix) / "paddle-worker"
WORKER_PYTHON = WORKER_ROOT / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
STATE = WORKER_ROOT / "ready.json"


def run(python: Path | str, *args: str) -> None:
    subprocess.run([str(python), *args], cwd=ROOT, check=True)


def pip(python, *args):
    run(python, "-m", "pip", "--disable-pip-version-check", *args)


def isolated(plan) -> bool:
    return platform.system() == "Windows" and plan.profile.startswith("cuda")


def verify(plan, formula: bool) -> None:
    # Model-free, no Paddle imports in the main process on the isolated path.
    gpu = plan.profile.startswith("cuda")
    code = (
        "import torch; print('PyTorch:',torch.__version__); "
        "print('CUDA:',torch.cuda.is_available()); "
        "print('MPS:',bool(getattr(torch.backends,'mps',None) "
        "and torch.backends.mps.is_available())); "
    )
    if gpu:
        code += (
            "assert torch.cuda.is_available(), 'CUDA Torch runtime is not usable'; "
            "print(torch.nn.Conv2d(1,2,3).cuda()(torch.ones(1,1,8,8,device='cuda')).sum().item())"
        )
    run(sys.executable, "-c", code)
    if not formula:
        return
    if isolated(plan):
        if not STATE.is_file() or json.loads(STATE.read_text())["profile"] != plan.profile:
            raise RuntimeError("Paddle GPU worker needs installation/validation")
        run(WORKER_PYTHON, "-I", "-u", str(WORKER_SCRIPT), "--check", "--require-gpu")
    else:
        run(sys.executable, "-c", (
            "import os; os.environ['PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK']='True'; "
            "from econ_research.parsing.formula_ocr import check_formula_dependencies; "
            "check_formula_dependencies()"
        ))


def guard_install() -> None:
    if Path(sys.prefix).name != "econ-research" or sys.version_info[:2] != (3, 11):
        raise RuntimeError("Run this installer with the econ-research Conda Python 3.11")
    try:
        urllib.request.urlopen("http://127.0.0.1:8000/health", timeout=2).close()
    except OSError:
        pass
    else:
        raise RuntimeError("Stop the running server before repairing its environment")


def install(plan, formula: bool) -> None:
    guard_install()
    try:
        importlib.metadata.distribution("paddlepaddle-gpu")
    except importlib.metadata.PackageNotFoundError:
        pass
    else:
        raise RuntimeError(
            "Legacy Paddle GPU is installed in the main environment. Stop the server and "
            "uninstall paddlepaddle-gpu before using managed setup."
        )
    wanted_torch = "torch" + (f"=={plan.torch_version}" if plan.torch_version else "")
    wanted_vision = "torchvision" + (
        f"=={plan.torchvision_version}" if plan.torchvision_version else ""
    )
    # Local build tags distinguish CUDA from CPU; pip otherwise considers them interchangeable.
    if plan.profile.startswith("cuda"):
        suffix = "+cu130" if plan.profile == "cuda13" else "+cu126"
        wanted_torch += suffix
        wanted_vision += suffix
    elif plan.profile == "cpu" and platform.system() in {"Windows", "Linux"}:
        wanted_torch += "+cpu"
        wanted_vision += "+cpu"
    pip(sys.executable, "install", wanted_torch, wanted_vision, "--index-url", plan.torch_index)
    extra = "dev" if not formula or isolated(plan) else "dev,formula"
    pip(sys.executable, "install", "-e", f".[{extra}]")
    if formula and isolated(plan):
        if not WORKER_PYTHON.is_file():
            run(sys.executable, "-m", "venv", str(WORKER_ROOT))
        # Exact official wheel URL; ordinary dependencies come from PyPI, not the slow CUDA index.
        cuda = "cu130" if plan.profile == "cuda13" else "cu126"
        wheel = (
            f"https://paddle-whl.cdn.bcebos.com/stable/{cuda}/paddlepaddle-gpu/"
            "paddlepaddle_gpu-3.3.1-cp311-cp311-win_amd64.whl"
        )
        pip(WORKER_PYTHON, "install", wheel, "paddleocr[doc-parser]==3.7.0",
            "paddlex==3.7.2", "ftfy>=6.1,<7", "numpy<2.4", "--index-url",
            "https://pypi.org/simple")
        run(WORKER_PYTHON, "-I", "-u", str(WORKER_SCRIPT), "--check", "--require-gpu")
        run(WORKER_PYTHON, "-m", "pip", "check")
        # Only publish a usable worker. A failed install retains the primary CPU path.
        STATE.write_text(json.dumps(asdict(plan), indent=2), encoding="utf-8")
    verify(plan, formula)
    run(sys.executable, "-m", "pip", "check")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--install", action="store_true")
    parser.add_argument("--without-formula", action="store_true")
    args = parser.parse_args()
    plan = detect_runtime()
    print(f"Runtime profile: {plan.profile}. {plan.reason}", flush=True)
    try:
        if args.install:
            install(plan, not args.without_formula)
        else:
            verify(plan, not args.without_formula)
    except (OSError, RuntimeError, subprocess.SubprocessError, ValueError, KeyError) as exc:
        print(f"Runtime setup/check failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
