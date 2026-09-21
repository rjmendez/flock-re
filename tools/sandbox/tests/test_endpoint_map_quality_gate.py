import json

from tools.sandbox import endpoint_map_quality_gate as gate


def test_assess_separates_valid_and_uncertain_hosts():
    rows = [("www.google.com", 5), ("hpnotiq.flock", 2), ("jame", 100)]
    assessment = gate._assess(rows)
    assert assessment["top_hosts_total"] == 3
    assert assessment["top_hosts_valid"] == 1
    assert assessment["top_hosts_uncertain"] == 2
    assert assessment["weighted_valid"] == 5
    assert assessment["weighted_uncertain"] == 102


def test_main_blocks_when_quality_thresholds_fail(tmp_path, monkeypatch, capsys):
    payload = {
        "global": {
            "endpoint_hosts_top": [
                ["jame", 100],
                ["www.google.com", 1],
            ]
        }
    }
    src = tmp_path / "analysis.json"
    src.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(
        "sys.argv",
        [
            "endpoint_map_quality_gate.py",
            "--analysis-json",
            str(src),
            "--min-valid-domain-ratio",
            "0.8",
            "--max-uncertain-token-ratio",
            "0.2",
            "--min-high-confidence-hosts",
            "1",
        ],
    )
    rc = gate.main()
    out = json.loads(capsys.readouterr().out)
    assert rc == 3
    assert out["blocked"] is True
    assert out["assessment"]["uncertain_token_ratio"] > 0.2
