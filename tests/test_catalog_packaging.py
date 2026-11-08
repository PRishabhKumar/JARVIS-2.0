import importlib.util
import json
from pathlib import Path
import pytest
from jarvis.storage.store import Store

ROOT = Path(__file__).resolve().parents[1]


def test_all_55_families_honestly_tracked(core):
    rows = json.loads((ROOT / "src/jarvis/catalog.json").read_text())
    assert len(rows) == 55
    assert sum(r["family_id"].startswith("source") for r in rows) == 35
    assert sum(r["family_id"].startswith("addition") for r in rows) == 20
    ids = {r["family_id"] for r in rows}
    for tool in core.registry.all():
        assert tool.spec.domain == "extra" or tool.spec.domain in ids
    for row in rows:
        assert row["release_blocker"]
        assert (row["status"] == "partial") == bool(row["registered_tools"])
        for name in row["registered_tools"]:
            assert core.registry.get(name)


def test_schema_export_matches_actual_registry(core):
    rows = json.loads((ROOT / "docs/tool-schemas.json").read_text())
    assert {row["tool_id"] for row in rows} == {t.spec.tool_id for t in core.registry.all()}


def test_database_restart_and_migration(tmp_path):
    path = tmp_path / "state.db"
    db = Store(path)
    assert db.db.execute("PRAGMA user_version").fetchone()[0] == 1
    assert db.reserve("session", "call", "hash", "system.get_time") is None
    db.close()
    restarted = Store(path)
    assert restarted.reserve("session", "call", "hash", "system.get_time") == ("hash", "started")
    restarted.close()


def test_database_competing_reservation(tmp_path):
    one, two = Store(tmp_path / "s.db"), Store(tmp_path / "s.db")
    assert one.reserve("s", "c", "binding", "system.get_time") is None
    assert two.reserve("s", "c", "binding", "system.get_time") == ("binding", "started")
    one.close()
    two.close()


def load_autostart():
    spec = importlib.util.spec_from_file_location("render_autostart", ROOT / "scripts/render_autostart.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("os_name", ["linux", "macos", "windows"])
def test_autostart_generation_not_installation(os_name):
    module = load_autostart()
    data = module.render(
        os_name, ["/absolute/python", "-m", "jarvis", "satellite", "--config", "/path with spaces/file.json"]
    )
    assert isinstance(data, bytes) and len(data) > 50
    if os_name == "macos":
        import plistlib

        assert plistlib.loads(data)["RunAtLoad"]
    if os_name == "windows":
        assert "LeastPrivilege" in data.decode("utf-16")


def test_autostart_rejects_line_injection():
    with pytest.raises(ValueError):
        load_autostart().render("linux", ["/python", "evil\nExecStart=/bin/sh"])
