# Resilience Analysis: Distributed Purchase Flow

## Scenario
Purchase splits across two services:
- **Currency Service** (this): Owns wallet balances
- **Inventory Service** (external): Grants items via HTTP API

### Constraints
- No shared transaction (no 2PC)
- Inventory API can timeout, fail, or process twice
- Must maintain exactly-once end-to-end

## Partial-Failure Window

```
Currency Service                    Inventory Service
     │                                    │
     ├─ Debit wallet (local TX) ─────────►│
     │                                    │
     │          [CRASH/NETWORK FAIL]      │
     │                                    │
     ▼                                    ▼
```

**Failure window:** Between wallet debit and inventory grant completion.

If crash occurs here: money deducted, item not granted → **inconsistent state**

## Solution: Saga Pattern with Outbox

### 1. Outbox Table (in Currency DB)
```sql
CREATE TABLE outbox (
    id INTEGER PRIMARY KEY,
    operation TEXT NOT NULL,      -- 'grant_item'
    payload JSON NOT NULL,        -- {player_id, item_id, purchase_id}
    status TEXT DEFAULT 'pending',-- pending | completed | failed | compensating
    created_at TIMESTAMP,
    processed_at TIMESTAMP
);
```

### 2. Purchase Flow
```python
def purchase(player_id, item_id, price):
    with transaction():
        # 1. Debit wallet
        update_wallet_balance(player_id, -price)
        
        # 2. Write to outbox (same transaction!)
        insert_outbox('grant_item', {
            'player_id': player_id,
            'item_id': item_id,
            'purchase_id': txn_id
        })
        
        # 3. Record in ledger
        insert_ledger('purchase', price, item_id, txn_id)
```

### 3. Background Processor (Currency Service)
```python
def process_outbox():
    for entry in select_pending_outbox():
        try:
            # Call Inventory Service with idempotency key
            inventory_client.grant_item(
                player_id=entry.payload.player_id,
                item_id=entry.payload.item_id,
                idempotency_key=f"purchase_{entry.payload.purchase_id}"
            )
            update_outbox_status(entry.id, 'completed')
        except PermanentFailure:
            # Compensate: refund wallet
            update_wallet_balance(entry.payload.player_id, +price)
            update_outbox_status(entry.id, 'compensated')
            insert_ledger('refund', price, entry.payload.item_id, entry.payload.purchase_id)
        except TransientFailure:
            # Retry later (exponential backoff)
            pass
```

### 4. Inventory Service Idempotency
```python
# Must implement same idempotency pattern
def grant_item(player_id, item_id, idempotency_key):
    if already_processed(idempotency_key):
        return cached_response()
    do_grant()
    cache_response()
```

## Why This Works

| Property | How Achieved |
|----------|--------------|
| **Atomic debit + outbox** | Single local transaction |
| **Exactly-once grant** | Inventory idempotency key = purchase_id |
| **Crash survival** | Outbox persists; processor retries on restart |
| **No money loss** | Compensation refunds on permanent failure |
| **No duplicate items** | Inventory deduplicates via idempotency key |

## Double-Grant Bug: Detection & Correction

### Scenario
Last week, a bug credited some players 2x currency.

### Detection (No Downtime)
```sql
-- Reconstruct expected balance from ledger
SELECT 
    w.player_id,
    w.balance AS actual_balance,
    COALESCE(SUM(CASE WHEN l.operation='credit' THEN l.amount ELSE 0 END), 0) -
    COALESCE(SUM(CASE WHEN l.operation='purchase' THEN l.amount ELSE 0 END), 0) AS expected_balance
FROM wallets w
LEFT JOIN ledger l ON w.player_id = l.player_id
GROUP BY w.player_id
HAVING actual_balance != expected_balance;
```

### Invariant
```
wallet.balance = SUM(credits) - SUM(debits)
```
**Always true** if ledger is complete and transactions atomic.

### Correction
```python
def correct_balance(player_id):
    expected = calculate_from_ledger(player_id)
    actual = get_wallet(player_id).balance
    delta = expected - actual
    
    if delta != 0:
        # Create correction ledger entry
        with transaction():
            update_wallet(player_id, delta)
            insert_ledger('correction', delta, None, f"correction_{batch_id}")
        notify_player(player_id, delta)
```

### What Would Have Caught It Sooner
1. **Real-time invariant monitoring** - Alert on `balance != ledger_sum`
2. **Periodic reconciliation job** - Nightly full audit
3. **Ledger immutability** - No direct balance edits, only via ledgered operations
4. **Unit test for idempotency** - Verify duplicate credit requests don't double balance

## Summary

| Concern | Approach |
|---------|----------|
| Distributed atomicity | Saga + Outbox |
| Duplicate prevention | Idempotency keys at both services |
| Crash recovery | Persistent outbox + background processor |
| Compensation | Refund wallet on permanent failure |
| Audit/debug | Ledger table reconstructs truth |
| Bug detection | Invariant monitoring (balance = ledger sum) |