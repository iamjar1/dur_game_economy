# Game Economy Service

A durable wallet/economy service for games ensuring exactly-once operations and crash recovery.

## Quick Start

### With Docker (Recommended)
```bash
docker-compose up --build
```

### Without Docker
```bash
pip install -r requirements.txt
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

Service runs at `http://localhost:8000` with API docs at `http://localhost:8000/docs`

## API Usage

### 1. Credit Wallet (Battle Payout)
```bash
curl -X POST http://localhost:8000/v1/wallets/player1/credit \
  -H "Content-Type: application/json" \
  -H "idempotency_key: credit_001" \
  -d '{"amount": 100, "reason": "Battle win"}'
```

Response:
```json
{ "success": true, "balance": 100, "transactionId": "txn_credit_001" }
```

### 2. Purchase Item
```bash
curl -X POST http://localhost:8000/v1/wallets/player1/purchase \
  -H "Content-Type: application/json" \
  -H "idempotency_key: purchase_001" \
  -d '{"itemId": "sword_of_fire", "price": 50}'
```

Response:
```json
{ "success": true, "balance": 50, "itemId": "sword_of_fire", "transactionId": "txn_purchase_001" }
```

### 3. Claim Reward
```bash
curl -X POST http://localhost:8000/v1/rewards/daily_bonus/claim \
  -H "Content-Type: application/json" \
  -H "idempotency_key: claim_001" \
  -d '{"playerId": "player1"}'
```

Response:
```json
{ "success": true, "rewardId": "daily_bonus", "claimedAt": "2026-06-29T12:00:00Z" }
```

### 4. Get Wallet
```bash
curl http://localhost:8000/v1/wallets/player1
```

Response:
```json
{ "playerId": "player1", "balance": 50, "inventory": ["sword_of_fire"], "claimedRewards": ["daily_bonus"] }
```

## Running Tests

```bash
pytest tests/ -v
```

### Test Coverage
- ✅ Credit/purchase/claim endpoints
- ✅ Idempotency (duplicate requests return same response)
- ✅ Concurrency (racing purchases on same wallet)
- ✅ Insufficient funds rejection
- ✅ Already claimed rejection
- ✅ Input validation (negative amounts, zero prices)

## Architecture

- **SQLite** with WAL mode for crash-safe transactions
- **Idempotency keys** (SHA-256) for exactly-once semantics
- **Atomic transactions** for purchase (debit + grant in single TX)
- **Row-level locking** via UPDATE for concurrency control
- **Ledger table** for full audit trail

## Key Features

✅ Exactly-once under retries  
✅ Crash durability (survives kill -9)  
✅ Concurrency correctness (no double-spend)  
✅ Input validation at boundary  
✅ Complete audit trail  

## API Contract

| Method | Path | Description |
|--------|------|-------------|
| POST | /v1/wallets/{playerId}/credit | Add currency |
| POST | /v1/wallets/{playerId}/purchase | Buy item (atomic) |
| POST | /v1/rewards/{rewardId}/claim | Claim one-time reward |
| GET | /v1/wallets/{playerId} | Get wallet state |

## Error Codes

| Code | Error | Description |
|------|-------|-------------|
| 400 | INSUFFICIENT_FUNDS | Balance < price |
| 400 | ALREADY_CLAIMED | Reward already claimed |
| 400 | PURCHASE_FAILED | Item already owned |
| 422 | VALIDATION_ERROR | Invalid input |