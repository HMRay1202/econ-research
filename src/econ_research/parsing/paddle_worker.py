"""Standalone Paddle process: execute by file path with the dedicated venv Python.

This module deliberately imports neither econ_research nor Torch. Stdout is a
line-delimited JSON protocol; library output and native diagnostics belong on stderr.
"""

from __future__ import annotations

import contextlib
import json
import os
import sys
from pathlib import Path

PREFIX = "ECON_PADDLE_RESULT:"
_dll_handles = []


def prepare_runtime() -> None:
    os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")
    if sys.platform != "win32":
        return
    root = Path(sys.prefix) / "Lib" / "site-packages" / "nvidia"
    paths = [root / "cu13" / "bin" / "x86_64", root / "cu13" / "bin"]
    paths.extend(root.glob("*/bin"))
    for path in dict.fromkeys(paths):
        if path.is_dir():
            _dll_handles.append(os.add_dll_directory(str(path)))
            os.environ["PATH"] = str(path) + os.pathsep + os.environ.get("PATH", "")


def libraries():
    prepare_runtime()
    import paddle
    from paddleocr import FormulaRecognition
    from paddlex.utils.deps import require_extra

    require_extra("ocr", obj_name="Formula OCR")
    return paddle, FormulaRecognition


def device_for(paddle) -> str:
    try:
        if paddle.is_compiled_with_cuda() and paddle.device.cuda.device_count() > 0:
            return "gpu:0"
    except Exception as exc:
        print(f"Paddle GPU detection failed; using CPU: {exc}", file=sys.stderr)
    return "cpu"


def smoke_check(require_gpu: bool = False) -> dict:
    paddle, _ = libraries()
    device = device_for(paddle)
    if require_gpu and device != "gpu:0":
        raise RuntimeError("Paddle GPU is installed but no usable GPU is available")
    paddle.set_device(device)
    # No model constructor/download. A real convolution also checks cuDNN/cuBLAS loading.
    value = paddle.nn.Conv2D(1, 2, 3)(paddle.ones([1, 1, 8, 8])).sum().item()
    return {"device": device, "paddle": paddle.__version__, "convolution": value}


def emit(result: dict) -> None:
    print(PREFIX + json.dumps(result, ensure_ascii=True), flush=True)


def serve() -> None:
    pipeline = None
    pipeline_key = None
    for line in sys.stdin:
        try:
            request = json.loads(line)
            image = Path(request["image"]).resolve(strict=True)
            cache = Path(request["cache_dir"]).resolve()
            model_name = request["model_name"]
            if Path(model_name).name != model_name or model_name in {".", ".."}:
                raise ValueError("Invalid model name")
            key = (model_name, str(cache))
            if pipeline_key is not None and key != pipeline_key:
                raise ValueError("Start a new worker when changing model/cache")
            with contextlib.redirect_stdout(sys.stderr):
                if pipeline is None:
                    os.environ["PADDLE_PDX_CACHE_HOME"] = str(cache)
                    paddle, constructor = libraries()
                    device = device_for(paddle)
                    kwargs = {"model_name": model_name, "device": device}
                    cached = cache / "official_models" / model_name
                    if (cached / "inference.pdiparams").is_file():
                        kwargs["model_dir"] = str(cached)
                    print(f"Paddle worker device: {device}; model: {model_name}", file=sys.stderr)
                    pipeline = constructor(**kwargs)
                    pipeline_key = key
                results = []
                for result in pipeline.predict(str(image)):
                    mapping = getattr(result, "json", result)
                    results.append(mapping() if callable(mapping) else mapping)
            emit({"results": results, "device": device})
        except Exception as exc:
            emit({"error": f"{type(exc).__name__}: {exc}"})


if __name__ == "__main__":
    if "--check" in sys.argv:
        try:
            with contextlib.redirect_stdout(sys.stderr):
                result = smoke_check("--require-gpu" in sys.argv)
            emit(result)
        except Exception as exc:
            emit({"error": f"{type(exc).__name__}: {exc}"})
            raise SystemExit(1) from exc
    else:
        serve()
