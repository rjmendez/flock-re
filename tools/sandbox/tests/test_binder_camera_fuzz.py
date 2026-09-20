import json
import subprocess

from tools.sandbox import binder_camera_fuzz


def test_build_steps_bounded():
    steps = binder_camera_fuzz._build_steps("media.camera", max_ops=99)
    assert 1 <= len(steps) <= 8
    assert steps[0] == ["service", "list"]


def test_discover_serial_none_when_no_device(monkeypatch):
    def fake_run(*_args, **_kwargs):
        return subprocess.CompletedProcess(args=[], returncode=0, stdout="List of devices attached\n", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert binder_camera_fuzz._discover_serial() == ""


def test_main_dry_run_json(monkeypatch, capsys):
    monkeypatch.setattr(binder_camera_fuzz, "_discover_serial", lambda: "emulator-5554")

    # invoke via argv for argparse path
    monkeypatch.setattr(
        "sys.argv",
        ["binder_camera_fuzz.py", "--json", "--service", "media.camera.proxy", "--max-ops", "2"],
    )
    out_rc = binder_camera_fuzz.main()
    captured = capsys.readouterr().out
    payload = json.loads(captured)
    assert out_rc == 0
    assert payload["dry_run"] is True
    assert payload["serial"] == "emulator-5554"
    assert payload["service"] == "media.camera.proxy"
    assert len(payload["commands"]) == 2
