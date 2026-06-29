import pytest
from fastapi.testclient import TestClient
from src.main import app
from src.database import get_db, init_db
import os
import tempfile

@pytest.fixture
def client():
    """Create test client with fresh database."""
    db_fd, db_path = tempfile.mkstemp()
    os.close(db_fd)
    old_db = os.environ.get("DATABASE_PATH")
    os.environ["DATABASE_PATH"] = db_path
    
    init_db()
    
    with TestClient(app) as client:
        yield client
    
    os.unlink(db_path)
    if old_db:
        os.environ["DATABASE_PATH"] = old_db
    else:
        del os.environ["DATABASE_PATH"]

def test_credit_wallet(client):
    """Test crediting wallet."""
    response = client.post(
        "/v1/wallets/player1/credit",
        json={"amount": 100, "reason": "Battle win"},
        headers={"idempotency-key": "test_credit_1"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] == True
    assert data["balance"] == 100
    assert "transactionId" in data

def test_purchase_item(client):
    """Test purchasing item."""
    client.post(
        "/v1/wallets/player1/credit",
        json={"amount": 200, "reason": "Initial"},
        headers={"idempotency-key": "test_init_1"}
    )
    
    response = client.post(
        "/v1/wallets/player1/purchase",
        json={"itemId": "sword", "price": 100},
        headers={"idempotency-key": "test_purchase_1"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] == True
    assert data["balance"] == 100
    assert data["itemId"] == "sword"

def test_insufficient_funds(client):
    """Test purchase with insufficient funds."""
    response = client.post(
        "/v1/wallets/player1/purchase",
        json={"itemId": "sword", "price": 100},
        headers={"idempotency-key": "test_insufficient_1"}
    )
    assert response.status_code == 400
    data = response.json()
    assert data["detail"]["error"] == "INSUFFICIENT_FUNDS"

def test_claim_reward(client):
    """Test claiming reward."""
    response = client.post(
        "/v1/rewards/daily_bonus/claim",
        json={"playerId": "player1"},
        headers={"idempotency-key": "test_claim_1"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] == True
    assert data["rewardId"] == "daily_bonus"

def test_claim_reward_twice(client):
    """Test claiming reward twice (should fail)."""
    client.post(
        "/v1/rewards/daily_bonus/claim",
        json={"playerId": "player1"},
        headers={"idempotency-key": "test_claim_twice_1"}
    )
    
    response = client.post(
        "/v1/rewards/daily_bonus/claim",
        json={"playerId": "player1"},
        headers={"idempotency-key": "test_claim_twice_2"}
    )
    assert response.status_code == 400
    data = response.json()
    assert data["detail"]["error"] == "ALREADY_CLAIMED"

def test_idempotency(client):
    """Test that duplicate requests return same result."""
    response1 = client.post(
        "/v1/wallets/player1/credit",
        json={"amount": 100, "reason": "Test"},
        headers={"idempotency-key": "test_idempotent_1"}
    )
    
    response2 = client.post(
        "/v1/wallets/player1/credit",
        json={"amount": 100, "reason": "Test"},
        headers={"idempotency-key": "test_idempotent_1"}
    )
    
    assert response1.json() == response2.json()
    wallet = client.get("/v1/wallets/player1").json()
    assert wallet["balance"] == 100

def test_concurrent_purchases(client):
    """Test concurrent purchases on same wallet."""
    client.post(
        "/v1/wallets/player1/credit",
        json={"amount": 150, "reason": "Initial"},
        headers={"idempotency-key": "test_concurrent_init"}
    )
    
    import concurrent.futures
    
    def purchase(i):
        return client.post(
            "/v1/wallets/player1/purchase",
            json={"itemId": f"item_{i}", "price": 100},
            headers={"idempotency-key": f"test_concurrent_{i}"}
        )
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(purchase, i) for i in range(2)]
        results = [f.result() for f in futures]
    
    successes = [r for r in results if r.status_code == 200]
    failures = [r for r in results if r.status_code == 400]
    
    assert len(successes) == 1
    assert len(failures) == 1
    
    wallet = client.get("/v1/wallets/player1").json()
    assert wallet["balance"] == 50

def test_get_wallet(client):
    """Test getting wallet state."""
    client.post(
        "/v1/wallets/player1/credit",
        json={"amount": 100, "reason": "Test"},
        headers={"idempotency-key": "test_get_init"}
    )
    client.post(
        "/v1/wallets/player1/purchase",
        json={"itemId": "sword", "price": 50},
        headers={"idempotency-key": "test_get_purchase"}
    )
    client.post(
        "/v1/rewards/bonus/claim",
        json={"playerId": "player1"},
        headers={"idempotency-key": "test_get_claim"}
    )
    
    response = client.get("/v1/wallets/player1")
    assert response.status_code == 200
    data = response.json()
    assert data["balance"] == 50
    assert "sword" in data["inventory"]
    assert "bonus" in data["claimedRewards"]

def test_negative_amount(client):
    """Test negative amount validation."""
    response = client.post(
        "/v1/wallets/player1/credit",
        json={"amount": -100, "reason": "Invalid"},
        headers={"idempotency-key": "test_negative_1"}
    )
    assert response.status_code == 422

def test_zero_price(client):
    """Test zero price validation."""
    response = client.post(
        "/v1/wallets/player1/purchase",
        json={"itemId": "free_item", "price": 0},
        headers={"idempotency-key": "test_zero_1"}
    )
    assert response.status_code == 422