"""
Tests for tasks API endpoints (in-memory CRUD).

The tasks store is module-level in-memory state shared across the test
session, so each test creates its own task and operates on the returned id
to stay independent of execution order.
"""
import pytest


class TestTasksEndpoints:
    """Test suite for tasks-related endpoints."""

    def test_get_all_tasks(self, client):
        """Test getting all tasks returns a list."""
        response = client.get("/api/tasks")
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)

    def test_create_task(self, client):
        """Test creating a task returns it with the expected structure."""
        response = client.post(
            "/api/tasks",
            json={"title": "Review Q4 levels", "priority": "high", "dueDate": "2026-08-01"},
        )
        assert response.status_code == 200

        task = response.json()
        assert "id" in task
        assert task["title"] == "Review Q4 levels"
        assert task["priority"] == "high"
        assert task["dueDate"] == "2026-08-01"
        # New tasks always start pending
        assert task["status"] == "pending"

    def test_create_task_defaults_priority_to_medium(self, client):
        """Test that omitting priority defaults to medium."""
        response = client.post(
            "/api/tasks",
            json={"title": "No priority given", "dueDate": "2026-08-05"},
        )
        assert response.status_code == 200
        assert response.json()["priority"] == "medium"

    def test_create_task_missing_required_field(self, client):
        """Test that omitting a required field returns a validation error."""
        response = client.post("/api/tasks", json={"title": "Missing due date"})
        assert response.status_code == 422

    def test_created_task_appears_in_list(self, client):
        """Test that a created task is retrievable via GET."""
        create = client.post(
            "/api/tasks",
            json={"title": "Findable task", "priority": "low", "dueDate": "2026-09-01"},
        )
        task_id = create.json()["id"]

        response = client.get("/api/tasks")
        ids = [t["id"] for t in response.json()]
        assert task_id in ids

    def test_toggle_task(self, client):
        """Test toggling flips status between pending and completed."""
        create = client.post(
            "/api/tasks",
            json={"title": "Toggle me", "priority": "medium", "dueDate": "2026-08-10"},
        )
        task_id = create.json()["id"]
        assert create.json()["status"] == "pending"

        # pending -> completed
        first = client.patch(f"/api/tasks/{task_id}")
        assert first.status_code == 200
        assert first.json()["status"] == "completed"

        # completed -> pending
        second = client.patch(f"/api/tasks/{task_id}")
        assert second.status_code == 200
        assert second.json()["status"] == "pending"

    def test_toggle_nonexistent_task(self, client):
        """Test toggling a task that doesn't exist returns 404."""
        response = client.patch("/api/tasks/task-nonexistent-999")
        assert response.status_code == 404

        data = response.json()
        assert "detail" in data
        assert "not found" in data["detail"].lower()

    def test_delete_task(self, client):
        """Test deleting a task removes it from the list."""
        create = client.post(
            "/api/tasks",
            json={"title": "Delete me", "priority": "high", "dueDate": "2026-08-20"},
        )
        task_id = create.json()["id"]

        response = client.delete(f"/api/tasks/{task_id}")
        assert response.status_code == 200
        assert response.json()["success"] is True

        # Confirm it is gone
        ids = [t["id"] for t in client.get("/api/tasks").json()]
        assert task_id not in ids

    def test_delete_nonexistent_task(self, client):
        """Test deleting a task that doesn't exist returns 404."""
        response = client.delete("/api/tasks/task-nonexistent-999")
        assert response.status_code == 404

        data = response.json()
        assert "detail" in data
        assert "not found" in data["detail"].lower()
