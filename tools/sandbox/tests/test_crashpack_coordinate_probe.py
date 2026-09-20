import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.sandbox.crashpack_coordinate_probe import collect_hits, iter_files


def test_collect_hits_keeps_normal_behavior(tmp_path):
    path = tmp_path / "coords.log"
    path.write_text(
        "latitude=12.34\nlongitude=56.78\ngps=nav\n",
        encoding="utf-8",
    )

    hits, samples, diagnostic = collect_hits(path, 3)

    assert diagnostic is None
    assert hits == 3
    assert [sample["text"] for sample in samples] == [
        "latitude=12.34",
        "longitude=56.78",
        "gps=nav",
    ]


def test_iter_files_ignores_symlink_escape(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    (root / "inside.log").write_text("latitude=1.23\n", encoding="utf-8")

    outside_dir = tmp_path / "outside"
    outside_dir.mkdir()
    (outside_dir / "secret.log").write_text("latitude=9.99\n", encoding="utf-8")

    symlink = root / "escape_link"
    symlink.symlink_to(outside_dir)

    listed = sorted(str(path.relative_to(root)) for path in iter_files(root))

    assert listed == ["inside.log"]


def test_collect_hits_reports_read_errors(monkeypatch, tmp_path):
    path = tmp_path / "no_read.log"
    path.write_text("latitude=1.23\n", encoding="utf-8")

    def boom(self, *args, **kwargs):
        raise OSError("permission denied")

    monkeypatch.setattr(Path, "open", boom)

    hits, samples, diagnostic = collect_hits(path, 3)

    assert hits == 0
    assert samples == []
    assert diagnostic is not None
    assert "Read error for" in diagnostic
    assert "permission denied" in diagnostic
