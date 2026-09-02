"""Persistent, bounded local IPC for Paddle; no GPU libraries loaded in the caller."""

from __future__ import annotations

import atexit
import json
import logging
import os
import queue
import subprocess
import sys
import threading
from pathlib import Path

logger = logging.getLogger(__name__)
PREFIX = "ECON_PADDLE_RESULT:"


def worker_python() -> Path | None:
    override = os.environ.get("ECON_RESEARCH_PADDLE_PYTHON")
    if override:
        path = Path(override).expanduser().resolve()
        if not path.is_file():
            raise RuntimeError(f"Configured Paddle worker Python does not exist: {path}")
        return path
    if sys.platform != "win32":
        return None
    path = Path(sys.prefix) / "paddle-worker" / "Scripts" / "python.exe"
    # An incomplete installation must not silently take over the CPU fallback.
    return path if path.is_file() and (path.parents[1] / "ready.json").is_file() else None


def worker_command(python: Path) -> list[str]:
    return [str(python), "-I", "-u", str(Path(__file__).with_name("paddle_worker.py"))]


def worker_environment() -> dict[str, str]:
    env = dict(os.environ)
    for name in ("PYTHONPATH", "PYTHONHOME"):
        env.pop(name, None)
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def check_worker(python: Path, *, require_gpu: bool = False) -> None:
    command = worker_command(python) + ["--check"]
    if require_gpu:
        command.append("--require-gpu")
    subprocess.run(command, env=worker_environment(), check=True, timeout=120)


class PaddleProcess:
    def __init__(self, python: Path, model_name: str, cache_dir: Path, timeout: float = 300):
        self.python = python
        self.model_name = model_name
        self.cache_dir = cache_dir.resolve()
        self.timeout = timeout
        self._process = None
        self._responses = queue.Queue()
        self._lock = threading.Lock()

    def _start(self) -> None:
        self._responses = queue.Queue()
        self._process = subprocess.Popen(
            worker_command(self.python), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            # Inherit stderr so model loading/progress appears in the backend terminal/log.
            stderr=None, text=True, encoding="utf-8", errors="replace", bufsize=1,
            env=worker_environment(),
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        atexit.register(self.close)
        threading.Thread(
            target=self._read, args=(self._process.stdout, self._responses), daemon=True,
        ).start()

    @staticmethod
    def _read(stream, responses) -> None:
        try:
            for line in stream:
                if line.startswith(PREFIX):
                    responses.put(line[len(PREFIX):])
                else:
                    logger.info("Paddle: %s", line.rstrip())
        finally:
            responses.put(None)

    def predict(self, image_path: str) -> list:
        with self._lock:
            if self._process is None or self._process.poll() is not None:
                self.close()
                self._start()
            try:
                request = {
                    "image": str(Path(image_path).resolve()), "model_name": self.model_name,
                    "cache_dir": str(self.cache_dir),
                }
                self._process.stdin.write(json.dumps(request) + "\n")
                self._process.stdin.flush()
                response = self._responses.get(timeout=self.timeout)
                if response is None:
                    self.close()
                    raise RuntimeError("Paddle worker exited; see backend log")
                result = json.loads(response)
                if "error" in result:
                    raise RuntimeError(result["error"])
                logger.info("Paddle formula recognition device: %s (isolated)", result["device"])
                return result["results"]
            except queue.Empty as exc:
                self.close()
                raise TimeoutError("Paddle formula recognition exceeded timeout") from exc
            except (BrokenPipeError, OSError, ValueError):
                self.close()
                raise

    def close(self) -> None:
        atexit.unregister(self.close)
        process, self._process = self._process, None
        if process is None:
            return
        if process.stdin:
            try:
                process.stdin.close()
            except OSError:
                pass
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=3)
        if process.stdout:
            process.stdout.close()
