import json

from offstage.cli import main


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
