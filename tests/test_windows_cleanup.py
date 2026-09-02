import os
import stat
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from econ_research.api import create_app
from econ_research.service import _retry_windows_readonly


@pytest.mark.skipif(os.name != "nt", reason="Real Windows read-only attributes")
@pytest.mark.parametrize("with_crop", [False, True])
def test_purge_windows_readonly_entries(service, sample_pdf, with_crop):
    paper = service.ingest(sample_pdf).paper
    report = service.deep_read(paper.id)
    directory = service.formula_diagnostics_dir / paper.id
    directory.mkdir()
    files = [Path(paper.pdf_path), Path(paper.markdown_path),
             service.generated_dir / f"deep-read-{report.id}.md"]
    if with_crop:
        crop = directory / "crop.png"
        crop.write_bytes(b"test-only crop")
        files.append(crop)
    entries = [*files, directory]
    try:
        for entry in entries:
            entry.chmod(stat.S_IREAD)
        response = TestClient(create_app(service)).delete(f"/api/papers/{paper.id}/purge")
        assert response.status_code == 204, response.text
        assert all(not entry.exists() for entry in entries)
        assert service.repository.get_paper(paper.id) is None
    finally:
        for entry in entries:
            if entry.exists():
                entry.chmod(stat.S_IWRITE)


@pytest.mark.skipif(os.name != "nt", reason="Windows access-denied recovery")
@pytest.mark.parametrize("case", ["outside", "root", "writable", "sharing", "retry_failure"])
def test_readonly_retry_does_not_bypass_other_failures(tmp_path, case):
    root = tmp_path / "managed"
    root.mkdir()
    path = (tmp_path if case == "outside" else root) / "file"
    if case == "root":
        path = root
    else:
        path.write_text("unchanged")
    error = PermissionError(13, "test access denied", str(path), 32 if case == "sharing" else 5)
    calls = []

    def operation(target):
        calls.append(target)
        raise PermissionError("still locked")

    try:
        if case != "writable":
            path.chmod(stat.S_IREAD)
        with pytest.raises(PermissionError):
            _retry_windows_readonly(operation, path, error, root)
        assert calls == ([path] if case == "retry_failure" else [])
        assert path.exists()
        if case != "writable":
            assert path.stat().st_file_attributes & stat.FILE_ATTRIBUTE_READONLY
    finally:
        path.chmod(stat.S_IWRITE)


def test_non_windows_failure_is_not_retried(tmp_path, monkeypatch):
    import econ_research.service as module

    path = tmp_path / "file"
    path.write_text("unchanged")
    called = []
    with monkeypatch.context() as patch:
        patch.setattr(module.os, "name", "posix")
        with pytest.raises(PermissionError):
            _retry_windows_readonly(called.append, path, PermissionError("denied"), tmp_path)
    assert not called
    assert path.read_text() == "unchanged"
