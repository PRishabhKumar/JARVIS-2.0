import asyncio
from pathlib import Path
import pytest
from jarvis.config import Settings, PathScope
from jarvis.contracts import ExecutionContext, Risk, ToolCall
from jarvis.orchestrator import AgentCoordinator
from jarvis.policy import PolicyGate
from jarvis.storage.store import Store
from jarvis.agents import filesystem_agent, app_agent
from jarvis.registry import ToolRegistry


@pytest.fixture
def test_env(tmp_path):
    settings = Settings(roots=[str(tmp_path)], state_dir=str(tmp_path / ".jarvis_state"))
    scope = PathScope([str(tmp_path)], [str(tmp_path / ".jarvis_state")])
    registry = ToolRegistry()
    filesystem_agent.register(registry, settings, scope)
    app_agent.register(registry, settings, scope)
    store = Store(tmp_path / ".jarvis_state" / "state.db")
    context = ExecutionContext(
        session_id="test-session",
        max_calls=50,
        maximum_effect="local_write",
    )
    gate = PolicyGate(lambda req: asyncio.sleep(0, result=True), threshold=Risk.R2)
    coordinator = AgentCoordinator(registry, gate, store, context)
    yield coordinator, scope, tmp_path
    store.close()


@pytest.mark.asyncio
async def test_locate_path(test_env):
    core, scope, tmp_path = test_env
    # Create test hierarchy
    folder = tmp_path / "my_project_folder"
    folder.mkdir()
    file_target = folder / "data_sheet.xlsx"
    file_target.write_text("dummy")

    # Locate directory
    res_dir = await core.dispatch(ToolCall(
        call_id="call-loc-1",
        name="filesystem.locate_path",
        arguments={"query": "my_project", "root": str(tmp_path), "type": "directory"},
    ))
    assert res_dir.status == "succeeded"
    assert res_dir.structured_data["found"] is True
    assert len(res_dir.structured_data["matches"]) >= 1
    assert "my_project_folder" in res_dir.structured_data["best_match"]

    # Locate file
    res_file = await core.dispatch(ToolCall(
        call_id="call-loc-2",
        name="filesystem.locate_path",
        arguments={"query": "data_sheet", "root": str(tmp_path), "type": "file"},
    ))
    assert res_file.status == "succeeded"
    assert res_file.structured_data["found"] is True
    assert "data_sheet.xlsx" in res_file.structured_data["best_match"]

    # Missing target
    res_missing = await core.dispatch(ToolCall(
        call_id="call-loc-3",
        name="filesystem.locate_path",
        arguments={"query": "completely_nonexistent_xyz", "root": str(tmp_path)},
    ))
    assert res_missing.status == "succeeded"
    assert res_missing.structured_data["found"] is False
    assert len(res_missing.structured_data["matches"]) == 0


@pytest.mark.asyncio
async def test_inspect_directory_categorization(test_env):
    core, scope, tmp_path = test_env
    test_dir = tmp_path / "mixed_files"
    test_dir.mkdir()
    (test_dir / "report1.docx").write_text("word1")
    (test_dir / "report2.doc").write_text("word2")
    (test_dir / "slides.pptx").write_text("presentation")
    (test_dir / "budget.xlsx").write_text("spreadsheet")
    (test_dir / "manual.pdf").write_text("pdf doc")
    (test_dir / "code.py").write_text("print(1)")

    res = await core.dispatch(ToolCall(
        call_id="call-inspect-1",
        name="filesystem.inspect_directory",
        arguments={"path": str(test_dir)},
    ))
    assert res.status == "succeeded"
    data = res.structured_data
    assert data["file_count"] == 6
    assert data["categories"]["Word"] == 2
    assert data["categories"]["PowerPoint"] == 1
    assert data["categories"]["Excel"] == 1
    assert data["categories"]["PDF"] == 1
    assert data["categories"]["Code"] == 1


@pytest.mark.asyncio
async def test_create_directory_and_move_items(test_env):
    core, scope, tmp_path = test_env
    source_dir = tmp_path / "src_folder"
    source_dir.mkdir()
    f1 = source_dir / "item1.txt"
    f2 = source_dir / "item2.txt"
    f1.write_text("1")
    f2.write_text("2")

    target_dir = tmp_path / "target_folder"

    # Create target directory
    res_mkdir = await core.dispatch(ToolCall(
        call_id="call-mkdir-1",
        name="filesystem.create_directory",
        arguments={"path": str(target_dir)},
    ))
    assert res_mkdir.status == "succeeded"
    assert target_dir.is_dir()

    # Move items
    res_move = await core.dispatch(ToolCall(
        call_id="call-move-1",
        name="filesystem.move_items",
        arguments={"sources": [str(f1), str(f2)], "destination": str(target_dir)},
    ))
    assert res_move.status == "succeeded"
    assert res_move.structured_data["moved_count"] == 2
    assert (target_dir / "item1.txt").is_file()
    assert (target_dir / "item2.txt").is_file()
    assert not f1.exists()
    assert not f2.exists()


@pytest.mark.asyncio
async def test_organize_by_type_category(test_env):
    core, scope, tmp_path = test_env
    abcd = tmp_path / "abcd"
    abcd.mkdir()
    (abcd / "doc1.docx").write_text("doc1")
    (abcd / "doc2.doc").write_text("doc2")
    (abcd / "deck.pptx").write_text("deck")
    (abcd / "finances.xlsx").write_text("finances")
    (abcd / "readme.txt").write_text("readme")

    res = await core.dispatch(ToolCall(
        call_id="call-org-1",
        name="filesystem.organize_by_type",
        arguments={"folder_path": str(abcd), "grouping": "category"},
    ))
    assert res.status == "succeeded"
    data = res.structured_data
    assert data["organized_count"] == 5
    assert (abcd / "Word" / "doc1.docx").is_file()
    assert (abcd / "Word" / "doc2.doc").is_file()
    assert (abcd / "PowerPoint" / "deck.pptx").is_file()
    assert (abcd / "Excel" / "finances.xlsx").is_file()
    assert (abcd / "Documents" / "readme.txt").is_file()
    assert data["summary"]["Word"] == 2
    assert data["summary"]["PowerPoint"] == 1
    assert data["summary"]["Excel"] == 1


@pytest.mark.asyncio
async def test_c_drive_guardrail():
    # Verify that any access to C: drive requires confirmation and is blocked if denied
    confirmed = False

    async def confirm_handler(req):
        nonlocal confirmed
        return confirmed

    gate = PolicyGate(confirm_handler, threshold=Risk.R2)

    class MockSpec:
        tool_id = "filesystem.list_directory"
        schema_hash = "mock_hash"
        risk = Risk.R0
        effect = "read"

    class MockTool:
        spec = MockSpec()
        preview = staticmethod(lambda args: f"Listing {args}")

    ctx = ExecutionContext(session_id="test", maximum_effect="local_write")

    # 1. Access to C: drive with denied confirmation
    confirmed = False
    call_c = ToolCall(call_id="c-call-1", name="filesystem.list_directory", arguments={"path": "C:\\Windows"})
    allowed, decision = await gate.authorize(MockTool(), call_c, ctx)
    assert allowed is False
    assert decision == "APPROVAL_DENIED"

    # 2. Access to C: drive with approved confirmation
    confirmed = True
    allowed, decision = await gate.authorize(MockTool(), call_c, ctx)
    assert allowed is True
    assert decision == "confirmed"

    # 3. Access to D: drive (non-C, non-deletion) is auto-allowed
    call_d = ToolCall(call_id="d-call-1", name="filesystem.list_directory", arguments={"path": "D:\\Projects"})
    allowed, decision = await gate.authorize(MockTool(), call_d, ctx)
    assert allowed is True
    assert decision == "allow"


@pytest.mark.asyncio
async def test_deletion_guardrail(test_env):
    core, scope, tmp_path = test_env
    test_file = tmp_path / "to_delete.txt"
    test_file.write_text("delete me")

    # 1. Denied deletion
    gate_deny = PolicyGate(lambda req: asyncio.sleep(0, result=False), threshold=Risk.R2)
    core_deny = AgentCoordinator(core.registry, gate_deny, core.store, core.context)
    res_deny = await core_deny.dispatch(ToolCall(
        call_id="call-del-1",
        name="filesystem.delete_items",
        arguments={"paths": [str(test_file)]},
    ))
    assert res_deny.status == "denied"
    assert test_file.exists()

    # 2. Approved deletion
    gate_approve = PolicyGate(lambda req: asyncio.sleep(0, result=True), threshold=Risk.R2)
    core_approve = AgentCoordinator(core.registry, gate_approve, core.store, core.context)
    res_approve = await core_approve.dispatch(ToolCall(
        call_id="call-del-2",
        name="filesystem.delete_items",
        arguments={"paths": [str(test_file)]},
    ))
    assert res_approve.status == "succeeded"
    assert not test_file.exists()


@pytest.mark.asyncio
async def test_app_open_target_validation(test_env):
    core, scope, tmp_path = test_env
    # Missing target
    res_missing = await core.dispatch(ToolCall(
        call_id="call-open-1",
        name="app.open_target",
        arguments={"target": str(tmp_path / "does_not_exist"), "application": "vscode"},
    ))
    assert res_missing.status == "failed"
    assert res_missing.error_code == "RESOURCE_NOT_FOUND" or res_missing.error_code == "TARGET_NOT_FOUND"
