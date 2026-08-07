import json

import pytest

from offstage.batch import MISSING, resolve
from offstage.driver import Driver
from offstage.manifest import Manifest


def make_driver(tmp_path, monkeypatch):
    monkeypatch.setenv("OFFSTAGE_DIR", str(tmp_path))
    mf = Manifest(name="App", bundle_id="dev.example.App",
                  app_path=tmp_path / "App.app", sock_path="/tmp/offstage-batch-test.sock")
    d = Driver.__new__(Driver)  # skip probe compilation in unit tests
    d.mf = mf
    d.bin = tmp_path
    d.mode = "ax"
    d.shots = tmp_path / "shots"
    d.shots.mkdir(exist_ok=True)
    d.cost_log = None
    return d


# ---------- JSON-pointer resolution ----------

def test_resolve_dotted_key_and_index():
    snap = {"defaults": {"notes.v1": [{"title": "A"}, {"title": "B"}]}}
    assert resolve(snap, "/defaults/notes.v1/1/title") == "B"


def test_resolve_whole_document():
    assert resolve({"a": 1}, "") == {"a": 1}


def test_resolve_missing_returns_sentinel():
    assert resolve({"a": {}}, "/a/b/c") is MISSING
    assert resolve({"a": []}, "/a/0") is MISSING
    assert resolve({"a": [1]}, "/a/x") is MISSING


def test_resolve_escapes():
    assert resolve({"a/b": {"~": 1}}, "/a~1b/~0") == 1


def test_resolve_rejects_relative_pointer():
    with pytest.raises(ValueError, match="JSON pointer"):
        resolve({}, "defaults/x")


# ---------- batch execution ----------

def test_batch_runs_steps_in_order(tmp_path, monkeypatch):
    d = make_driver(tmp_path, monkeypatch)
    seen = []
    monkeypatch.setattr(Driver, "launch", lambda self, reset: seen.append(f"launch{reset}") or True)
    monkeypatch.setattr(Driver, "press", lambda self, i: seen.append(f"press{i}") or "done")
    monkeypatch.setattr(Driver, "pid", lambda self: 42)
    out = d.batch([["start"], ["press", "addNote"]])
    assert seen == ["launchTrue", "pressaddNote"]
    assert out["ok"] is True
    assert [s["verb"] for s in out["steps"]] == ["start", "press"]
    assert out["app_alive"] is True


def test_batch_expect_passes_on_ground_truth(tmp_path, monkeypatch):
    d = make_driver(tmp_path, monkeypatch)
    monkeypatch.setattr(Driver, "defaults_json", lambda self: {"notes.v1": [{"title": "A"}]})
    monkeypatch.setattr(Driver, "port_cmd", lambda self, o, **k: {"titles": ["A"]})
    monkeypatch.setattr(Driver, "pid", lambda self: 42)
    out = d.batch([["expect", "/defaults/notes.v1/0/title", '"A"'],
                   ["expect", "/port/titles", '["A"]']])
    assert out["ok"] is True
    assert all(s["ok"] for s in out["steps"])


def test_batch_expect_failure_stops_and_reports(tmp_path, monkeypatch):
    d = make_driver(tmp_path, monkeypatch)
    monkeypatch.setattr(Driver, "defaults_json", lambda self: {"notes.v1": []})
    monkeypatch.setattr(Driver, "port_cmd", lambda self, o, **k: {})
    monkeypatch.setattr(Driver, "pid", lambda self: 42)
    ran = []
    monkeypatch.setattr(Driver, "press", lambda self, i: ran.append(i) or "done")
    out = d.batch([["expect", "/defaults/notes.v1/0/title", '"A"'], ["press", "addNote"]])
    assert out["ok"] is False
    assert ran == []  # stops at the first failure
    bad = out["steps"][0]
    assert bad["ok"] is False and bad["want"] == "A" and bad["got"] == "<missing>"
    assert out["failed_step"] == 0


def test_batch_continue_on_error_runs_rest(tmp_path, monkeypatch):
    d = make_driver(tmp_path, monkeypatch)
    monkeypatch.setattr(Driver, "defaults_json", lambda self: {})
    monkeypatch.setattr(Driver, "port_cmd", lambda self, o, **k: {})
    monkeypatch.setattr(Driver, "pid", lambda self: 42)
    ran = []
    monkeypatch.setattr(Driver, "press", lambda self, i: ran.append(i) or "done")
    out = d.batch([["expect", "/defaults/x", '"A"'], ["press", "addNote"]], stop=False)
    assert out["ok"] is False
    assert ran == ["addNote"]


def test_batch_dead_app_fails_the_step(tmp_path, monkeypatch):
    """A crash mid-batch is a finding, not a silent continue."""
    d = make_driver(tmp_path, monkeypatch)
    monkeypatch.setattr(Driver, "press", lambda self, i: "done app_alive=False")
    monkeypatch.setattr(Driver, "pid", lambda self: None)
    out = d.batch([["press", "boom"], ["press", "after"]])
    assert out["ok"] is False and out["app_alive"] is False
    assert "app died" in out["steps"][0]["error"]
    assert len(out["steps"]) == 1


def test_batch_unknown_verb_is_a_step_error(tmp_path, monkeypatch):
    d = make_driver(tmp_path, monkeypatch)
    monkeypatch.setattr(Driver, "pid", lambda self: 42)
    out = d.batch([["fly", "away"]])
    assert out["ok"] is False and "unknown" in out["steps"][0]["error"]


def test_batch_observe_and_golden_pass_through(tmp_path, monkeypatch):
    d = make_driver(tmp_path, monkeypatch)
    monkeypatch.setattr(Driver, "observe", lambda self: '{"ax":[]}')
    monkeypatch.setattr(Driver, "golden", lambda self, make=False: f"make={make}")
    monkeypatch.setattr(Driver, "pid", lambda self: 42)
    out = d.batch([["observe"], ["golden", "check"], ["golden", "bake"]])
    assert out["steps"][0]["out"] == '{"ax":[]}'
    assert out["steps"][1]["out"] == "make=False"
    assert out["steps"][2]["out"] == "make=True"


def test_batch_rejects_non_list_steps(tmp_path, monkeypatch):
    d = make_driver(tmp_path, monkeypatch)
    with pytest.raises(ValueError, match="list of"):
        d.batch({"press": "addNote"})


def test_batch_json_is_serializable(tmp_path, monkeypatch):
    d = make_driver(tmp_path, monkeypatch)
    monkeypatch.setattr(Driver, "pid", lambda self: 42)
    monkeypatch.setattr(Driver, "defaults_json", lambda self: {"k": "v"})
    monkeypatch.setattr(Driver, "port_cmd", lambda self, o, **k: {})
    json.dumps(d.batch([["expect", "/defaults/k", '"v"']]))
