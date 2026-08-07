import json

import pytest

from offstage.cli import main
from offstage.driver import Driver


def test_validate_ok(tmp_path, capsys):
    mf = tmp_path / "m.json"
    mf.write_text(json.dumps({
        "name": "App", "bundle_id": "dev.example.App",
        "app_path": "/tmp/App.app", "sock_path": "/tmp/a.sock",
    }))
    assert main(["validate", str(mf)]) == 0
    out = capsys.readouterr().out
    assert "ok" in out
    assert "warn" in out  # app_path doesn't exist


def test_validate_bad(tmp_path, capsys):
    mf = tmp_path / "m.json"
    mf.write_text(json.dumps({"name": "App"}))
    assert main(["validate", str(mf)]) == 1
    assert "INVALID" in capsys.readouterr().out


def test_bad_manifest_on_verb(tmp_path, capsys):
    mf = tmp_path / "m.json"
    mf.write_text("{broken")
    assert main(["observe", str(mf)]) == 64


@pytest.fixture
def manifest(tmp_path):
    mf = tmp_path / "m.json"
    mf.write_text(json.dumps({
        "name": "App", "bundle_id": "dev.example.App",
        "app_path": "/tmp/App.app", "sock_path": "/tmp/offstage-cli-test.sock",
    }))
    return str(mf)


@pytest.fixture
def fake_batch(monkeypatch):
    """Record what the CLI hands the driver, without touching a real app."""
    calls = {}
    monkeypatch.setattr(Driver, "__init__", lambda self, mf, **kw: None)

    def batch(self, steps, stop=True):
        calls["steps"], calls["stop"] = steps, stop
        return {"ok": True, "steps": [], "app_alive": True}

    monkeypatch.setattr(Driver, "batch", batch)
    return calls


def test_batch_inline_json(manifest, fake_batch, capsys):
    assert main(["batch", manifest, '[["press","addNote"]]']) == 0
    assert fake_batch["steps"] == [["press", "addNote"]]
    assert json.loads(capsys.readouterr().out)["ok"] is True


def test_batch_from_file(tmp_path, manifest, fake_batch):
    steps = tmp_path / "steps.json"
    steps.write_text('[["start"]]')
    assert main(["batch", manifest, str(steps)]) == 0
    assert fake_batch["steps"] == [["start"]]


def test_batch_from_stdin(manifest, fake_batch, monkeypatch):
    import io
    monkeypatch.setattr("sys.stdin", io.StringIO('[["stop"]]'))
    assert main(["batch", manifest, "-"]) == 0
    assert fake_batch["steps"] == [["stop"]]


def test_batch_keep_going_flag(manifest, fake_batch):
    main(["batch", manifest, '[["start"]]'])
    assert fake_batch["stop"] is True
    main(["batch", manifest, '[["start"]]', "--keep-going"])
    assert fake_batch["stop"] is False


def test_batch_failure_exit_code(manifest, monkeypatch):
    monkeypatch.setattr(Driver, "__init__", lambda self, mf, **kw: None)
    monkeypatch.setattr(Driver, "batch", lambda self, steps, stop=True: {
        "ok": False, "steps": [], "app_alive": True, "failed_step": 0})
    assert main(["batch", manifest, '[["press","x"]]']) == 1


def test_batch_missing_steps_file(manifest, capsys):
    assert main(["batch", manifest, "/tmp/definitely-absent-steps.json"]) == 64
    assert "no such steps file" in capsys.readouterr().out


def test_batch_bad_json(manifest, capsys):
    assert main(["batch", manifest, "[[broken"]) == 64
    assert "not valid JSON" in capsys.readouterr().out


def test_batch_bad_step_shape(manifest, monkeypatch, capsys):
    monkeypatch.setattr(Driver, "__init__", lambda self, mf, **kw: None)
    assert main(["batch", manifest, '{"press":"x"}']) == 64
    assert "list of" in capsys.readouterr().out
