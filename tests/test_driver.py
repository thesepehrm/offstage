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


def _with_processes(driver, rows):
    driver._processes = lambda: rows  # noqa: SLF001 — stubbing the pgrep call


def test_pid_prefers_the_instance_holding_this_manifest_socket(tmp_path, monkeypatch):
    d = make_driver(tmp_path, monkeypatch, sock="/tmp/mine.sock")
    _with_processes(d, [
        (100, "/other/Build/App.app/Contents/MacOS/App -uitest-port /tmp/theirs.sock"),
        (200, f"{d.mf.app_path}/Contents/MacOS/App -uitest-port /tmp/mine.sock"),
    ])
    assert d.pid() == 200


def test_pid_falls_back_to_the_manifest_app_path(tmp_path, monkeypatch):
    d = make_driver(tmp_path, monkeypatch, sock="/tmp/mine.sock")
    _with_processes(d, [
        (100, "/other/Build/App.app/Contents/MacOS/App"),
        (200, f"{d.mf.app_path}/Contents/MacOS/App"),
    ])
    assert d.pid() == 200


def test_pid_is_none_when_several_strangers_and_none_is_ours(tmp_path, monkeypatch):
    """Better no target than an arbitrary one: picking `.first` here is what
    made launch kill another checkout's app."""
    d = make_driver(tmp_path, monkeypatch, sock="/tmp/mine.sock")
    _with_processes(d, [
        (100, "/a/App.app/Contents/MacOS/App -uitest-port /tmp/a.sock"),
        (101, "/b/App.app/Contents/MacOS/App -uitest-port /tmp/b.sock"),
    ])
    assert d.pid() is None


def test_pid_takes_a_lone_process_without_markers(tmp_path, monkeypatch):
    d = make_driver(tmp_path, monkeypatch, sock="/tmp/mine.sock")
    _with_processes(d, [(100, "/somewhere/App.app/Contents/MacOS/App")])
    assert d.pid() == 100


def test_target_is_the_pid_when_known(tmp_path, monkeypatch):
    d = make_driver(tmp_path, monkeypatch, sock="/tmp/mine.sock")
    _with_processes(d, [(200, f"{d.mf.app_path}/Contents/MacOS/App -uitest-port /tmp/mine.sock")])
    assert d.target() == "200"


def test_target_falls_back_to_the_bundle_id(tmp_path, monkeypatch):
    d = make_driver(tmp_path, monkeypatch, sock="/tmp/mine.sock")
    _with_processes(d, [])
    assert d.target() == "dev.example.App"


def test_stranger_note_names_the_other_bundle(tmp_path, monkeypatch):
    d = make_driver(tmp_path, monkeypatch, sock="/tmp/mine.sock")
    _with_processes(d, [
        (200, f"{d.mf.app_path}/Contents/MacOS/App -uitest-port /tmp/mine.sock"),
        (100, "/other/Build/App.app/Contents/MacOS/App -uitest-port /tmp/theirs.sock"),
    ])
    note = d.stranger_note()
    assert "1 other App process" in note
    assert "/other/Build/App.app" in note


def test_stranger_note_is_empty_when_alone(tmp_path, monkeypatch):
    d = make_driver(tmp_path, monkeypatch, sock="/tmp/mine.sock")
    _with_processes(d, [(200, f"{d.mf.app_path}/Contents/MacOS/App -uitest-port /tmp/mine.sock")])
    assert d.stranger_note() == ""


def test_processes_parses_ps_output(tmp_path, monkeypatch):
    """Guards the shell contract: BSD pgrep cannot print arguments, so the pid
    list and the command lines come from two different commands."""
    d = make_driver(tmp_path, monkeypatch, sock="/tmp/mine.sock")
    calls = []

    def fake_sh(*cmd, timeout=60):
        calls.append([str(c) for c in cmd])
        if cmd[0] == "pgrep":
            return "100\n200"
        return "  100 /a/App.app/Contents/MacOS/App -uitest-port /tmp/a.sock\n" \
               "  200 /b/App.app/Contents/MacOS/App -uitest-port /tmp/mine.sock"

    d.sh = fake_sh
    assert d._processes() == [
        (100, "/a/App.app/Contents/MacOS/App -uitest-port /tmp/a.sock"),
        (200, "/b/App.app/Contents/MacOS/App -uitest-port /tmp/mine.sock"),
    ]
    assert calls[0][:2] == ["pgrep", "-x"]
    assert calls[1][0] == "ps" and calls[1][-1] == "100,200"
    assert d.pid() == 200


def test_processes_empty_when_nothing_matches(tmp_path, monkeypatch):
    d = make_driver(tmp_path, monkeypatch, sock="/tmp/mine.sock")
    d.sh = lambda *cmd, timeout=60: ""
    assert d._processes() == []
    assert d.pid() is None
