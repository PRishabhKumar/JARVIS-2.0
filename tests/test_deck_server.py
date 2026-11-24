import pytest
from fastapi.testclient import TestClient
from jarvis.config import Settings
from jarvis.deck_server import create_deck_app


@pytest.fixture
def deck_client(tmp_path):
    settings = Settings(
        roots=[str(tmp_path)],
        state_dir=str(tmp_path / "state"),
        allow_mutations=True,
    )
    app = create_deck_app(settings)
    return TestClient(app)


def test_deck_rest_health(deck_client):
    res = deck_client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["protocol"] == "jarvis.ui.v1"
    assert data["name"] == "JARVIS"


def test_deck_rest_capabilities(deck_client):
    res = deck_client.get("/capabilities")
    assert res.status_code == 200
    data = res.json()
    assert "capabilities" in data
    assert len(data["capabilities"]) > 0
    first = data["capabilities"][0]
    assert "id" in first
    assert "description" in first
    assert "risk" in first
    assert "effect" in first
    assert "os" in first


def test_deck_rest_telemetry(deck_client):
    res = deck_client.get("/telemetry")
    assert res.status_code == 200
    telem = res.json()
    for field in ("cpu", "ram", "ram_used_gb", "ram_total_gb", "plugged", "supported_controls"):
        assert field in telem
    assert isinstance(telem["supported_controls"], list)


def test_deck_websocket_session_handshake(deck_client):
    with deck_client.websocket_connect("/ws") as ws:
        # Handshake
        ws.send_json({
            "type": "session.hello",
            "protocol": "jarvis.ui.v1",
            "client_id": "desktop-ui",
        })
        m1 = ws.receive_json()
        assert m1["type"] == "session.ready"
        assert m1["protocol"] == "jarvis.ui.v1"
        assert "session_id" in m1

        m2 = ws.receive_json()
        assert m2["type"] == "agent.state"

        m3 = ws.receive_json()
        assert m3["type"] == "telemetry.update"

        # Ping-pong
        ws.send_json({"type": "ping", "id": "ping-test-123"})
        m4 = ws.receive_json()
        assert m4["type"] == "pong"
        assert m4["ping_id"] == "ping-test-123"


def test_deck_websocket_controls(deck_client):
    with deck_client.websocket_connect("/ws") as ws:
        ws.send_json({
            "type": "session.hello",
            "protocol": "jarvis.ui.v1",
            "client_id": "desktop-ui",
        })
        ws.receive_json()  # session.ready
        ws.receive_json()  # agent.state
        ws.receive_json()  # telemetry.update

        # Send control request
        ws.send_json({
            "type": "control.request",
            "request_id": "ctrl-test-1",
            "control": "volume",
            "value": 45,
        })

        res = ws.receive_json()
        assert res["type"] == "telemetry.update"
        assert "telemetry" in res
