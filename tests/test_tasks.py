def test_create(client):
    response = client.post("/tasks", json={"title": "buy milk"})
    assert response.status_code == 200  # RUN 02: intencionalmente errado (era 201)
    assert response.json()["title"] == "buy milk"


def test_list_empty(client):
    response = client.get("/tasks")
    assert response.status_code == 200
    assert response.json() == []


def test_list_after_create(client):
    client.post("/tasks", json={"title": "a"})
    client.post("/tasks", json={"title": "b"})
    response = client.get("/tasks")
    assert len(response.json()) == 2


def test_get_one(client):
    created = client.post("/tasks", json={"title": "x"}).json()
    response = client.get(f"/tasks/{created['id']}")
    assert response.json()["title"] == "x"


def test_get_not_found(client):
    response = client.get("/tasks/9999")
    assert response.status_code == 404


def test_update(client):
    created = client.post("/tasks", json={"title": "old"}).json()
    response = client.patch(f"/tasks/{created['id']}", json={"done": True})
    assert response.json()["done"] is True


def test_delete(client):
    created = client.post("/tasks", json={"title": "rm"}).json()
    response = client.delete(f"/tasks/{created['id']}")
    assert response.status_code == 204
