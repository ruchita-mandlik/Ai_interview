import pytest

def test_register_user(client):
    response = client.post(
        "/api/auth/register",
        json={
            "name": "Test User",
            "email": "test@example.com",
            "password": "password123",
            "confirm_password": "password123",
            "target_role": "Java Developer",
            "experience_level": "Intermediate",
            "skills": "Java, Spring Boot"
        }
    )
    assert response.status_code == 201
    data = response.json()
    assert "access_token" in data
    assert data["user"]["email"] == "test@example.com"
    assert data["user"]["name"] == "Test User"

def test_register_duplicate_email(client):
    user_payload = {
        "name": "Test User",
        "email": "dup@example.com",
        "password": "password123",
        "confirm_password": "password123"
    }
    client.post("/api/auth/register", json=user_payload)
    resp = client.post("/api/auth/register", json=user_payload)
    assert resp.status_code == 400
    assert "already exists" in resp.json()["detail"].lower()

def test_login_user(client):
    user_payload = {
        "name": "Login User",
        "email": "login@example.com",
        "password": "secretpassword",
        "confirm_password": "secretpassword"
    }
    client.post("/api/auth/register", json=user_payload)

    resp = client.post(
        "/api/auth/login",
        json={
            "email": "login@example.com",
            "password": "secretpassword"
        }
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data

def test_unauthorized_access(client):
    resp = client.get("/api/auth/me")
    assert resp.status_code == 401
