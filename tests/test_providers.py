import hashlib
import sys
import zipfile
from unittest.mock import patch
import pytest
from jarvis.config import Settings
from jarvis.bootstrap import build_registry
from jarvis.contracts import ExecutionContext
from jarvis.policy import PolicyGate
from jarvis.agents.archive_agent import safe_member
from jarvis.providers.broker import CommandBroker


async def request(core, name, arguments=None):
    return await core.dispatch({"call_id": name, "name": name, "arguments": arguments or {}})


@pytest.mark.parametrize(
    "name",
    [
        "system.get_time",
        "hardware.inventory",
        "memory.diagnostics",
        "health.battery",
        "clock.inspect",
        "process.list",
        "process.zombies",
        "network.connections",
        "network.ports",
        "network.interfaces",
        "network.diagnostics",
        "software.python_inventory",
        "packages.detect",
        "environment.inspect",
        "drivers.linux_modules",
        "security.linux_capabilities",
        "ipc.inspect",
        "services.status",
        "mounts.list",
        "app.list_allowlisted",
    ],
)
async def test_read_provider_normalization(core, name):
    result = await request(core, name)
    assert result.status in {"succeeded", "unsupported", "denied"}
    assert not result.execution_uncertain
    if result.status == "succeeded":
        assert result.verified
    else:
        assert result.error_code


async def test_file_tools(core, tmp_path):
    (tmp_path / "hello.txt").write_bytes(b"hello")
    for name, args in [
        ("filesystem.list_directory", {"path": "."}),
        ("filesystem.get_metadata", {"path": "hello.txt"}),
        ("filesystem.search_names", {"path": ".", "query": "hello"}),
        ("storage.analyze", {"path": "."}),
        ("filesystem.symlink_audit", {"path": "."}),
        ("permissions.inspect", {"path": "hello.txt"}),
    ]:
        result = await request(core, name, args)
        assert result.status == "succeeded", result
    checksum = await request(core, "integrity.sha256", {"path": "hello.txt"})
    assert checksum.structured_data["sha256"] == hashlib.sha256(b"hello").hexdigest()


async def test_zip_inspection_no_extraction(core, tmp_path):
    path = tmp_path / "archive.zip"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("../escape.txt", "malicious")
        z.writestr("normal.txt", "data")
    result = await request(core, "archive.inspect", {"path": "archive.zip"})
    assert result.status == "succeeded"
    assert result.structured_data["unsafe_count"] == 1
    assert not (tmp_path / "normal.txt").exists()


@pytest.mark.parametrize("name", ["/etc/passwd", "../x", "foo/../../x", "C:/x", r"foo\bar"])
def test_archive_paths(name):
    assert not safe_member(name)


async def test_archive_bad_file(core, tmp_path):
    (tmp_path / "bad.zip").write_bytes(b"not a zip")
    result = await request(core, "archive.inspect", {"path": "bad.zip"})
    assert result.error_code == "ARCHIVE_INVALID"


async def test_environment_never_exposes_values(core, monkeypatch):
    monkeypatch.setenv("CUSTOM_SAFE_LOOKING_NAME", "secret_value_1234")
    result = await request(core, "environment.inspect")
    assert "secret_value_1234" not in result.model_dump_json()
    assert result.structured_data["values_redacted"]


async def test_app_deny_by_default(core):
    result = await request(core, "app.launch_allowlisted", {"app_id": "calculator"})
    assert result.error_code == "EFFECT_CEILING"


async def test_app_approval_not_implicit(core):
    core.context = ExecutionContext(session_id="write-task", maximum_effect="local_write")
    result = await request(core, "app.launch_allowlisted", {"app_id": "calculator"})
    assert result.error_code == "APPROVAL_DENIED"


async def test_app_unknown_even_with_approval(core):
    core.context = ExecutionContext(session_id="write-task", maximum_effect="local_write")

    async def approved(req):
        return True

    core.gate = PolicyGate(approved)
    result = await request(core, "app.launch_allowlisted", {"app_id": "calculator"})
    assert result.error_code == "APP_NOT_ALLOWLISTED"


async def test_app_fake_process_verification(core, tmp_path):
    settings = Settings(
        roots=[str(tmp_path)], state_dir=str(tmp_path / ".private"), apps={"test-app": [sys.executable]}
    )
    core.registry = build_registry(settings)
    core.context = ExecutionContext(session_id="write-task", maximum_effect="local_write")

    async def approved(req):
        assert "test-app" in req.preview
        return True

    core.gate = PolicyGate(approved)

    class Fake:
        pid = 9876

        def poll(self):
            return None

        def create_time(self):
            return 12.0

        def is_running(self):
            return True

    with patch("psutil.Popen", return_value=Fake()), patch("psutil.Process", return_value=Fake()):
        result = await request(core, "app.launch_allowlisted", {"app_id": "test-app"})
    assert result.verified and result.changed_resources == ["process:9876"]


async def test_process_identity_tools(core):
    import os

    for name in ("process.ancestry", "process.priority"):
        result = await request(core, name, {"pid": os.getpid()})
        assert result.status == "succeeded"


async def test_broker_rejects_unregistered_profile():
    with pytest.raises(FileNotFoundError):
        await CommandBroker().run("rm -rf /")


async def test_broker_fixed_argv_only():
    # Test fixture program is developer-owned. There is no model string interpolation.
    broker = CommandBroker({"test": [sys.executable, "-c", 'print("fixture")']})
    code, text = await broker.run("test")
    assert code == 0 and text.strip() == "fixture"


async def test_broker_output_cap():
    broker = CommandBroker({"test": [sys.executable, "-c", 'print("x"*25000)']})
    with pytest.raises(ValueError):
        await broker.run("test")


async def test_linux_only_capabilities_elsewhere(core, monkeypatch):
    monkeypatch.setattr("platform.system", lambda: "Darwin")
    for name in ("ipc.inspect", "security.linux_capabilities", "drivers.linux_modules"):
        assert (await request(core, name)).status == "unsupported"


async def test_windows_zombie_is_not_emulated(core, monkeypatch):
    monkeypatch.setattr("platform.system", lambda: "Windows")
    assert (await request(core, "process.zombies")).status == "unsupported"


async def test_services_windows_contract(monkeypatch):
    from jarvis.providers.status import services

    class Service:
        def name(self):
            return "fixture-service"

        def status(self):
            return "running"

    monkeypatch.setattr("platform.system", lambda: "Windows")
    monkeypatch.setattr("psutil.win_service_iter", lambda: iter([Service()]), raising=False)
    result = await services()
    assert result.structured_data["provider"] == "Windows SCM/psutil"


async def test_services_macos_contract(monkeypatch):
    from jarvis.providers.status import services

    monkeypatch.setattr("platform.system", lambda: "Darwin")
    monkeypatch.setattr("shutil.which", lambda x: "/bin/launchctl")

    async def fake(self, profile):
        assert self.profiles["services"] == ["/bin/launchctl", "list"]
        return 0, "PID Status Label\n- 0 example"

    monkeypatch.setattr(CommandBroker, "run", fake)
    result = await services()
    assert result.status == "succeeded"


async def test_services_init_detection(monkeypatch):
    from jarvis.providers.status import services

    monkeypatch.setattr("platform.system", lambda: "Linux")
    monkeypatch.setattr("shutil.which", lambda x: None)
    result = await services()
    assert result.error_code == "SYSTEMD_NOT_ACTIVE"
