import json

import pytest

from offstage.manifest import Golden, Manifest, ManifestError, validate

VALID = {
    "name": "App",
    "bundle_id": "dev.example.App",
    "app_path": "/tmp/App.app",
    "sock_path": "/tmp/app.sock",
    "canonical_fixture": [
        ["press", "addNote"],
        ["menu", "File", "Delete Note"],
        ["port", "{\"cmd\":\"state\"}"],
        ["sleep", "0.5"],
    ],
    "goldens": [{"name": "wide", "size": "1000x600", "file": "goldens/wide.png"}],
    "a11y_baseline": {"unlabelled_buttons": 0},
}


def test_valid():
    assert validate(VALID) == []


def test_missing_required():
    errs = validate({"name": "x"})
    assert any("bundle_id" in e for e in errs)
    assert any("app_path" in e for e in errs)
    assert any("sock_path" in e for e in errs)


def test_unknown_verb():
    raw = dict(VALID, canonical_fixture=[["click", "button"]])
    assert any("unknown verb 'click'" in e for e in validate(raw))


def test_port_payload_must_be_json():
    raw = dict(VALID, canonical_fixture=[["port", "{nope"]])
    assert any("port payload" in e for e in validate(raw))


def test_menu_arity():
    raw = dict(VALID, canonical_fixture=[["menu", "File"]])
    assert any("menu takes exactly" in e for e in validate(raw))


def test_bad_golden_size():
    raw = dict(VALID, goldens=[{"name": "w", "size": "big", "file": "g.png"}])
    assert any("size must look like" in e for e in validate(raw))


def test_threshold_inside_noise_band_rejected():
    # ~0.08% is the measured first-run SCK capture noise; thresholds below it
    # false-alarm on clean runs.
    raw = dict(VALID, golden_threshold_pct=0.05)
    assert any("noise band" in e for e in validate(raw))
    assert validate(dict(VALID, golden_threshold_pct=0.1)) == []
    assert validate(dict(VALID, golden_threshold_pct=0)) == []


def test_load_resolves_paths_against_manifest_dir(tmp_path):
    mf_file = tmp_path / "app.manifest.json"
    mf_file.write_text(json.dumps(VALID))
    mf = Manifest.load(mf_file)
    assert mf.goldens[0].file == tmp_path / "goldens/wide.png"
    assert str(mf.app_path) == "/tmp/App.app"  # absolute stays absolute


def test_load_rejects_invalid(tmp_path):
    mf_file = tmp_path / "bad.manifest.json"
    mf_file.write_text(json.dumps({"name": "x"}))
    with pytest.raises(ManifestError):
        Manifest.load(mf_file)


def test_load_rejects_non_json(tmp_path):
    mf_file = tmp_path / "bad.json"
    mf_file.write_text("{nope")
    with pytest.raises(ManifestError):
        Manifest.load(mf_file)


def test_golden_dimensions():
    g = Golden("wide", "1000x600", None)
    assert (g.width, g.height) == (1000, 600)
