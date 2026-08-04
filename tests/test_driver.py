import datetime
import json
import socket
import threading

import pytest

from offstage.driver import Driver
from offstage.manifest import Golden, Manifest


def make_driver(tmp_path, monkeypatch, sock="/tmp/offstage-test.sock"):
    monkeypatch.setenv("OFFSTAGE_DIR", str(tmp_path))
    mf = Manifest(name="App", bundle_id="dev.example.App",
                  app_path=tmp_path / "App.app", sock_path=sock)
    d = Driver.__new__(Driver)  # skip probe compilation in unit tests
    d.mf = mf
    d.bin = tmp_path
    d.mode = "ax"
    d.shots = tmp_path / "shots"
    d.shots.mkdir(exist_ok=True)
    d.cost_log = None
    return d


def test_jsonable_binary_json_roundtrip():
    notes = json.dumps([{"title": "A"}]).encode()
    assert Driver._jsonable(notes) == [{"title": "A"}]


def test_jsonable_small_binary_hexed():
    out = Driver._jsonable(b"\x00\x01")
    assert out == {"_bytes_hex": "0001"}


def test_jsonable_large_binary_dropped():
    out = Driver._jsonable(b"\xff" * 300)
    assert "dropped" in out


def test_jsonable_dates_and_nesting():
    d = datetime.datetime(2026, 1, 1)
    assert Driver._jsonable({"a": [d]}) == {"a": ["2026-01-01T00:00:00"]}


def test_dispatch_unknown_verb(tmp_path, monkeypatch):
    d = make_driver(tmp_path, monkeypatch)
    with pytest.raises(ValueError, match="unknown driver verb"):
        d.dispatch("click", ["x"])


def test_dispatch_sleep(tmp_path, monkeypatch):
    d = make_driver(tmp_path, monkeypatch)
    assert d.dispatch("sleep", ["0"]) == ""


def test_port_cmd_roundtrip(tmp_path, monkeypatch):
    """port_cmd speaks line-JSON to a UNIX socket server."""
    sock_path = "/tmp/offstage-py-test.sock"
    d = make_driver(tmp_path, monkeypatch, sock=sock_path)

    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        import os
        try:
            os.unlink(sock_path)
        except FileNotFoundError:
            pass
        server.bind(sock_path)
        server.listen(1)

        def serve():
            conn, _ = server.accept()
            buf = b""
            while b"\n" not in buf:
                buf += conn.recv(4096)
            req = json.loads(buf)
            conn.sendall((json.dumps({"echo": req["cmd"]}) + "\n").encode())
            conn.close()

        t = threading.Thread(target=serve, daemon=True)
        t.start()
        assert d.port_cmd({"cmd": "state"}) == {"echo": "state"}
        t.join(timeout=5)
    finally:
        server.close()


def test_port_cmd_no_server(tmp_path, monkeypatch):
    d = make_driver(tmp_path, monkeypatch, sock="/tmp/offstage-absent.sock")
    reply = d.port_cmd({"cmd": "state"}, timeout=0.5)
    assert "error" in reply


def test_golden_reports_missing_golden_file(tmp_path, monkeypatch):
    """golden() must say 'bake first', not diff against nothing."""
    d = make_driver(tmp_path, monkeypatch)
    d.mf.goldens = [Golden("wide", "100x100", tmp_path / "absent.png")]
    monkeypatch.setattr(Driver, "launch", lambda self, reset: True)
    monkeypatch.setattr(Driver, "pid", lambda self: 12345)
    monkeypatch.setattr(Driver, "probe", lambda self, *a, **k: "")
    monkeypatch.setattr("time.sleep", lambda s: None)
    out = d.golden()
    assert "NO GOLDEN" in out
