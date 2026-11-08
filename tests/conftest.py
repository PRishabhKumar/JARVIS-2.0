import pytest
from jarvis.config import Settings
from jarvis.bootstrap import build_registry
from jarvis.contracts import ExecutionContext
from jarvis.policy import PolicyGate
from jarvis.storage.store import Store
from jarvis.orchestrator import AgentCoordinator


@pytest.fixture
def core(tmp_path):
    settings = Settings(roots=[str(tmp_path)], state_dir=str(tmp_path / ".private"))
    store = Store(tmp_path / ".private" / "state.db")
    coordinator = AgentCoordinator(
        build_registry(settings), PolicyGate(), store, ExecutionContext(session_id="test-session")
    )
    yield coordinator
    store.close()
