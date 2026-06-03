import pytest


@pytest.mark.parametrize("i", range(100))
def test_create_many(client, i):
    response = client.post("/tasks", json={"title": f"task-{i}"})
    assert response.status_code == 201
    assert response.json()["title"] == f"task-{i}"
