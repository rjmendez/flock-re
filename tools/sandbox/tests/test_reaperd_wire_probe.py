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
