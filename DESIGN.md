# Architecture & Design Decisions

## Technology Stack

### Language: Python + FastAPI
**Why:** Rapid development, automatic OpenAPI docs, built-in validation via Pydantic, excellent testing ecosystem.

### Database: SQLite
**Why:** 
- File-based (no separate server to manage)
- ACID transactions with WAL mode for crash safety
- Row-level locking via `SELECT ... FOR UPDATE` equivalent (implicit in UPDATE)
- Meets all requirements for this assessment scope
- **Trade-off:** Not suitable for high-concurrency production; PostgreSQL would be chosen there

## Database Schema

| Table | Purpose | Key Constraints |
|-------|---------|-----------------|
| `wallets` | Player balances | `CHECK (balance >= 0)` prevents negative |
| `inventory` | Owned items | `UNIQUE(player_id, item_id)` prevents duplicates |
| `claimed_rewards` | One-time rewards | Composite PK `(player_id, reward_id)` |
| `idempotency_keys` | Deduplication | TTL via `expires_at` (48h retention) |
| `ledger` | Audit trail | Immutable append-only |

## Idempotency Strategy

### Key Generation
```python
key = SHA256(f"{player_id}:{operation}:{json.dumps(request_data, sort_keys=True)}")
```

### Flow
1. Client sends request with `Idempotency-Key` header
2. Server generates deterministic key from request
3. Check `idempotency_keys` table for existing key
4. **If found:** Return cached response (no re-execution)
5. **If not found:** Execute operation, store response, return result

### Retention
- **48 hours** (configurable)
- Hourly cleanup job removes expired keys
- Rationale: Covers typical retry windows (network issues, client retries)

## Atomicity & Durability

### Purchase Operation (Critical Path)
```sql
BEGIN;
  INSERT OR IGNORE INTO wallets (player_id, balance) VALUES (?, 0);
  SELECT balance FROM wallets WHERE player_id = ?;  -- implicit lock
  UPDATE wallets SET balance = balance - ? WHERE player_id = ?;
  INSERT INTO inventory (player_id, item_id) VALUES (?, ?);
  INSERT INTO ledger (...) VALUES (...);
COMMIT;
```

### Crash Safety (kill -9)
- **WAL mode** + `PRAGMA synchronous=FULL` = durable commits
- Incomplete transactions auto-rollback on restart
- **All-or-nothing:** Debit and grant are in same transaction
- Retry after crash: idempotency key returns cached response or re-executes

### Isolation Level
- SQLite default: **SERIALIZABLE** (transactions appear sequential)
- Writers block other writers on same row
- Readers never block (MVCC via WAL)

## Concurrency Control

### Problem
Two purchases racing on balance=150, price=100 each → only one should succeed.

### Solution
- `UPDATE wallets SET balance = balance - ?` implicitly locks row
- Second writer blocks until first commits/rolls back
- Second sees updated balance (50) → fails check → returns error

### Result
- Exactly one succeeds
- No double-spend, no lost update, no negative balance

## API Contract

### Success Responses
```json
// POST /credit
{ "success": true, "balance": 150, "transactionId": "txn_abc123" }

// POST /purchase
{ "success": true, "balance": 50, "itemId": "sword", "transactionId": "txn_def456" }

// POST /claim
{ "success": true, "rewardId": "daily_bonus", "claimedAt": "2026-06-29T12:00:00Z" }

// GET /wallet
{ "playerId": "p1", "balance": 50, "inventory": ["sword"], "claimedRewards": ["daily_bonus"] }
```

### Error Responses
| Code | Error | When |
|------|-------|------|
| 400 | INSUFFICIENT_FUNDS | Balance < price |
| 400 | ALREADY_CLAIMED | Reward already claimed |
| 400 | PURCHASE_FAILED | Item already owned |
| 422 | VALIDATION_ERROR | Invalid input (negative, zero, missing) |

### Limits
- Max balance: 2,147,483,647 (SQLite INTEGER)
- Max string length: 255 chars
- Idempotency retention: 48 hours