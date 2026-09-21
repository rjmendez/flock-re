import json

from tools.sandbox import reaperd_wire_probe as probe


def test_reports_blocked_when_socket_missing(monkeypatch, capsys):
    monkeypatch.setattr(probe, "_discover_serial", lambda: "emulator-5554")

    def fake_shell(_serial, shell_cmd, _timeout):
        if "test -S" in shell_cmd:
            return (0, "1", "")
        return (0, "0", "")

    monkeypatch.setattr(probe, "_adb_shell", fake_shell)
    monkeypatch.setattr("sys.argv", ["reaperd_wire_probe.py", "--json"])
    rc = probe.main()
    out = json.loads(capsys.readouterr().out)
    assert rc == 3
    assert out["blocked"] is True
    assert "Missing runtime socket" in out["blockers"][0]


def test_virtualized_mode_allows_missing_socket(monkeypatch, capsys):
    monkeypatch.setattr(probe, "_discover_serial", lambda: "emulator-5554")
    monkeypatch.setattr(
        probe,
        "_target_fingerprint",
        lambda *_args, **_kwargs: "vendor/flock/device:9/PQ3A/123:user/release-keys",
    )

    def fake_shell(_serial, shell_cmd, _timeout):
        if "test -S" in shell_cmd:
            return (0, "1", "")
        if "command -v toybox" in shell_cmd:
            return (0, "0", "")
        if "grep -i reaperd" in shell_cmd:
            return (0, "1", "")
        return (0, "0", "")

    monkeypatch.setattr(probe, "_adb_shell", fake_shell)
    monkeypatch.setattr(
        "sys.argv",
        ["reaperd_wire_probe.py", "--json", "--virtualized-allow-missing-socket"],
    )
    rc = probe.main()
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert out["ok"] is True
    assert out["virtualized_override"] is True


def test_aosp_profile_marks_lane_not_applicable(monkeypatch, capsys):
    monkeypatch.setattr(probe, "_discover_serial", lambda: "emulator-5554")
    monkeypatch.setattr(
        probe,
        "_target_fingerprint",
        lambda *_args, **_kwargs: "google/sdk_gphone_x86/generic_x86:8.1.0/OSM/userdebug/dev-keys",
    )

    def fake_shell(_serial, shell_cmd, _timeout):
        if "test -S" in shell_cmd:
            return (0, "1", "")
        if "command -v toybox" in shell_cmd:
            return (0, "0", "")
        if "grep -i reaperd" in shell_cmd:
            return (0, "1", "")
        return (0, "0", "")

    monkeypatch.setattr(probe, "_adb_shell", fake_shell)
    monkeypatch.setattr("sys.argv", ["reaperd_wire_probe.py", "--json"])
    rc = probe.main()
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert out["ok"] is True
    assert out["lane_applicability"] == "not_applicable_on_aosp_emulator"
