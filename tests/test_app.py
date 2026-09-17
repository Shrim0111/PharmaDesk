from datetime import date, timedelta

from fastapi.testclient import TestClient

from app.database import Base, engine
from app.main import app


Base.metadata.create_all(bind=engine)

client = TestClient(app)


def test_health():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_register_and_login():
    email = "testuser@example.com"
    password = "password123"

    register_response = client.post(
        "/auth/register",
        json={
            "email": email,
            "password": password,
        },
    )

    assert register_response.status_code in [200, 201, 400]

    login_response = client.post(
        "/auth/login",
        data={
            "username": email,
            "password": password,
        },
    )

    assert login_response.status_code == 200

    token = login_response.json()["access_token"]

    assert token
    assert login_response.json()["token_type"] == "bearer"


def test_create_medicine():
    email = "medicine_test@example.com"
    password = "password123"

    client.post(
        "/auth/register",
        json={
            "email": email,
            "password": password,
        },
    )

    login_response = client.post(
        "/auth/login",
        data={
            "username": email,
            "password": password,
        },
    )

    assert login_response.status_code == 200

    token = login_response.json()["access_token"]

    response = client.post(
        "/medicines",
        headers={
            "Authorization": f"Bearer {token}",
        },
        json={
            "name": "Paracetamol",
            "sku": "PARA-500",
            "reorder_threshold": 10,
        },
    )

    assert response.status_code in [200, 201]

    medicine = response.json()

    assert medicine["name"] == "Paracetamol"
    assert medicine["sku"] == "PARA-500"
    assert medicine["reorder_threshold"] == 10


def test_create_batch_and_check_stock():
    email = "batch_test@example.com"
    password = "password123"

    client.post(
        "/auth/register",
        json={
            "email": email,
            "password": password,
        },
    )

    login_response = client.post(
        "/auth/login",
        data={
            "username": email,
            "password": password,
        },
    )

    assert login_response.status_code == 200

    token = login_response.json()["access_token"]

    headers = {
        "Authorization": f"Bearer {token}",
    }

    medicine_response = client.post(
        "/medicines",
        headers=headers,
        json={
            "name": "Ibuprofen",
            "sku": "IBU-200",
            "reorder_threshold": 5,
        },
    )

    assert medicine_response.status_code in [200, 201]

    medicine_id = medicine_response.json()["id"]

    future_date = (date.today() + timedelta(days=30)).isoformat()

    batch_response = client.post(
        "/batches",
        headers=headers,
        json={
            "medicine_id": medicine_id,
            "batch_no": "IBU-B001",
            "quantity": 20,
            "expiry_date": future_date,
        },
    )

    assert batch_response.status_code in [200, 201]

    stock_response = client.get(
        f"/medicines/{medicine_id}/stock",
        headers=headers,
    )

    assert stock_response.status_code == 200

    stock = stock_response.json()

    assert stock["total_sellable_stock"] == 20


def test_fefo_dispensing():
    email = "fefo_test@example.com"
    password = "password123"

    client.post(
        "/auth/register",
        json={
            "email": email,
            "password": password,
        },
    )

    login_response = client.post(
        "/auth/login",
        data={
            "username": email,
            "password": password,
        },
    )

    assert login_response.status_code == 200

    token = login_response.json()["access_token"]

    headers = {
        "Authorization": f"Bearer {token}",
    }

    medicine_response = client.post(
        "/medicines",
        headers=headers,
        json={
            "name": "Aspirin",
            "sku": "ASP-100",
            "reorder_threshold": 5,
        },
    )

    assert medicine_response.status_code in [200, 201]

    medicine_id = medicine_response.json()["id"]

    later_expiry = (date.today() + timedelta(days=60)).isoformat()
    earlier_expiry = (date.today() + timedelta(days=20)).isoformat()

    first_batch = client.post(
        "/batches",
        headers=headers,
        json={
            "medicine_id": medicine_id,
            "batch_no": "ASP-LATE",
            "quantity": 10,
            "expiry_date": later_expiry,
        },
    )

    assert first_batch.status_code in [200, 201]

    second_batch = client.post(
        "/batches",
        headers=headers,
        json={
            "medicine_id": medicine_id,
            "batch_no": "ASP-EARLY",
            "quantity": 10,
            "expiry_date": earlier_expiry,
        },
    )

    assert second_batch.status_code in [200, 201]

    dispense_response = client.post(
        f"/medicines/{medicine_id}/dispense",
        headers=headers,
        json={
            "quantity": 6,
        },
    )

    assert dispense_response.status_code == 200

    result = dispense_response.json()

    assert result["dispensed"] == 6

    stock_response = client.get(
        f"/medicines/{medicine_id}/stock",
        headers=headers,
    )

    assert stock_response.status_code == 200

    stock = stock_response.json()

    assert stock["total_sellable_stock"] == 14