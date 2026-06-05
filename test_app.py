import pytest
import fakeredis
import app as server


@pytest.fixture(autouse=True)
def fake_redis(monkeypatch):
    r = fakeredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(server, "r", r)
    return r


@pytest.fixture()
def client():
    server.app.config["TESTING"] = True
    with server.app.test_client() as c:
        yield c


@pytest.fixture()
def queue(client):
    res = client.post("/queue")
    return res.get_json()


# ── /health ──────────────────────────────────────────────────────────────────

def test_health(client):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.get_json() == {"status": "ok"}


# ── POST /queue ───────────────────────────────────────────────────────────────

def test_create_queue_status(client):
    res = client.post("/queue")
    assert res.status_code == 201


def test_create_queue_returns_ids(client):
    data = client.post("/queue").get_json()
    assert "sender_id" in data
    assert "recipient_id" in data


def test_create_queue_ids_are_unique(client):
    a = client.post("/queue").get_json()
    b = client.post("/queue").get_json()
    assert a["sender_id"] != b["sender_id"]
    assert a["recipient_id"] != b["recipient_id"]


# ── POST /send ────────────────────────────────────────────────────────────────

def test_send_message(client, queue):
    res = client.post(f"/send/{queue['sender_id']}", json={"message": "hello"})
    assert res.status_code == 200
    assert res.get_json() == {"status": "sent"}


def test_send_invalid_sender(client):
    res = client.post("/send/nonexistent", json={"message": "hello"})
    assert res.status_code == 404


def test_send_missing_message_field(client, queue):
    res = client.post(f"/send/{queue['sender_id']}", json={"text": "oops"})
    assert res.status_code == 400


def test_send_no_body(client, queue):
    res = client.post(f"/send/{queue['sender_id']}", content_type="application/json", data="")
    assert res.status_code == 400


# ── GET /receive ──────────────────────────────────────────────────────────────

def test_receive_message(client, queue):
    client.post(f"/send/{queue['sender_id']}", json={"message": "hello"})
    res = client.get(f"/receive/{queue['recipient_id']}")
    assert res.status_code == 200
    assert res.get_json()["message"] == "hello"


def test_receive_empty_queue(client, queue):
    res = client.get(f"/receive/{queue['recipient_id']}")
    assert res.status_code == 200
    assert res.get_json()["message"] is None


def test_receive_is_fifo(client, queue):
    for msg in ["first", "second", "third"]:
        client.post(f"/send/{queue['sender_id']}", json={"message": msg})
    results = [client.get(f"/receive/{queue['recipient_id']}").get_json()["message"] for _ in range(3)]
    assert results == ["first", "second", "third"]


def test_receive_invalid_recipient(client):
    res = client.get("/receive/nonexistent")
    assert res.status_code == 404


def test_receive_pops_only_one(client, queue):
    client.post(f"/send/{queue['sender_id']}", json={"message": "a"})
    client.post(f"/send/{queue['sender_id']}", json={"message": "b"})
    client.get(f"/receive/{queue['recipient_id']}")
    res = client.get(f"/receive/{queue['recipient_id']}")
    assert res.get_json()["message"] == "b"


# ── GET /receive/drain ────────────────────────────────────────────────────────

def test_drain_all_messages(client, queue):
    for msg in ["a", "b", "c"]:
        client.post(f"/send/{queue['sender_id']}", json={"message": msg})
    res = client.get(f"/receive/{queue['recipient_id']}/drain")
    assert res.status_code == 200
    assert res.get_json()["messages"] == ["a", "b", "c"]


def test_drain_empty_queue(client, queue):
    res = client.get(f"/receive/{queue['recipient_id']}/drain")
    assert res.status_code == 200
    assert res.get_json()["messages"] == []


def test_drain_clears_queue(client, queue):
    client.post(f"/send/{queue['sender_id']}", json={"message": "hi"})
    client.get(f"/receive/{queue['recipient_id']}/drain")
    res = client.get(f"/receive/{queue['recipient_id']}/drain")
    assert res.get_json()["messages"] == []


def test_drain_invalid_recipient(client):
    res = client.get("/receive/nonexistent/drain")
    assert res.status_code == 404


# ── queue isolation ───────────────────────────────────────────────────────────

def test_queues_are_isolated(client):
    q1 = client.post("/queue").get_json()
    q2 = client.post("/queue").get_json()
    client.post(f"/send/{q1['sender_id']}", json={"message": "for q1"})
    res = client.get(f"/receive/{q2['recipient_id']}")
    assert res.get_json()["message"] is None
