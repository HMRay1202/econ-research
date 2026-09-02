import json
import os
import sys
from pathlib import Path

import pytest

from econ_research.parsing import paddle_process, paddle_worker


@pytest.mark.parametrize("fail", [False, True])
def test_document_parse_always_releases_worker(monkeypatch, tmp_path, fail):
    from types import SimpleNamespace

    from econ_research.parsing.docling_parser import DoclingParser

    closed = []
    parser = object.__new__(DoclingParser)
    parser._formula_enricher = SimpleNamespace(
        recognizer=SimpleNamespace(close=lambda: closed.append(True))
    )

    def parse(*args):
        if fail:
            raise ValueError("parse failed")
        return "document"

    monkeypatch.setattr(parser, "_parse", parse)
    if fail:
        with pytest.raises(ValueError, match="parse failed"):
            parser.parse(tmp_path / "paper.pdf")
    else:
        assert parser.parse(tmp_path / "paper.pdf") == "document"
    assert closed == [True]


def fake_worker(monkeypatch, tmp_path, body):
    script = tmp_path / "fake worker.py"
    script.write_text(body, encoding="utf-8")
    monkeypatch.setattr(
        paddle_process, "worker_command", lambda python: [sys.executable, "-u", str(script)]
    )
    return paddle_process.PaddleProcess(Path(sys.executable), "test", tmp_path)


def test_worker_reuses_process_and_closes_on_eof(monkeypatch, tmp_path):
    worker = fake_worker(monkeypatch, tmp_path, """
import json, sys
for line in sys.stdin:
    req = json.loads(line)
    print('model progress')
    print('ECON_PADDLE_RESULT:' + json.dumps({'results': [{'rec_formula': 'x=1'}],
                                          'device': 'gpu:0'}), flush=True)
""")
    try:
        assert worker.predict(str(tmp_path / "中文 crop.png")) == [{"rec_formula": "x=1"}]
        process = worker._process
        worker.predict(str(tmp_path / "second.png"))
        assert worker._process is process
    finally:
        worker.close()
    assert process.poll() == 0


def test_worker_timeout_terminates_only_owned_process(monkeypatch, tmp_path):
    worker = fake_worker(monkeypatch, tmp_path, "import time; time.sleep(30)")
    worker.timeout = 0.1
    with pytest.raises(TimeoutError):
        worker.predict(str(tmp_path / "a.png"))
    assert worker._process is None


def test_worker_crash_is_reported(monkeypatch, tmp_path):
    worker = fake_worker(monkeypatch, tmp_path, "raise SystemExit(3)")
    try:
        with pytest.raises(RuntimeError, match="exited"):
            worker.predict(str(tmp_path / "a.png"))
    finally:
        worker.close()


def test_worker_error_is_reported(monkeypatch, tmp_path):
    worker = fake_worker(monkeypatch, tmp_path, """
import sys
for line in sys.stdin:
    print('ECON_PADDLE_RESULT:{"error":"model failed"}', flush=True)
""")
    try:
        with pytest.raises(RuntimeError, match="model failed"):
            worker.predict(str(tmp_path / "a.png"))
    finally:
        worker.close()


def test_unfinished_worker_is_not_selected(monkeypatch, tmp_path):
    monkeypatch.delenv("ECON_RESEARCH_PADDLE_PYTHON", raising=False)
    monkeypatch.setattr(sys, "prefix", str(tmp_path))
    monkeypatch.setattr(sys, "platform", "win32")
    python = tmp_path / "paddle-worker/Scripts/python.exe"
    python.parent.mkdir(parents=True)
    python.touch()
    assert paddle_process.worker_python() is None
    (python.parents[1] / "ready.json").write_text("{}")
    assert paddle_process.worker_python() == python


def test_worker_env_removes_python_path_injection(monkeypatch):
    monkeypatch.setenv("PYTHONPATH", "other-env")
    monkeypatch.setenv("PYTHONHOME", "other-env")
    assert "PYTHONPATH" not in paddle_process.worker_environment()
    assert "PYTHONHOME" not in paddle_process.worker_environment()
    assert os.environ["PYTHONPATH"] == "other-env"


def test_worker_lazy_model_and_explicit_cache(monkeypatch, tmp_path, capsys):
    import io
    from types import SimpleNamespace

    crop = tmp_path / "crop.png"
    crop.touch()
    model_dir = tmp_path / "official_models/test"
    model_dir.mkdir(parents=True)
    (model_dir / "inference.pdiparams").touch()
    calls = []

    class Model:
        def __init__(self, **kwargs):
            calls.append(kwargs)

        def predict(self, image):
            return [{"rec_formula": "x=1"}]

    paddle = SimpleNamespace(is_compiled_with_cuda=lambda: False)
    monkeypatch.setattr(paddle_worker, "libraries", lambda: (paddle, Model))
    monkeypatch.setenv("PADDLE_PDX_CACHE_HOME", "unused")
    request = json.dumps({"image": str(crop), "cache_dir": str(tmp_path), "model_name": "test"})
    monkeypatch.setattr(sys, "stdin", io.StringIO(request + "\n" + request + "\n"))
    paddle_worker.serve()
    assert len(calls) == 1
    assert calls[0]["model_dir"] == str(model_dir)
    assert capsys.readouterr().out.count(paddle_worker.PREFIX) == 2
