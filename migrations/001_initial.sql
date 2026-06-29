-- Wallets: stores player balances
CREATE TABLE IF NOT EXISTS wallets (
    player_id TEXT PRIMARY KEY,
    balance INTEGER NOT NULL DEFAULT 0 CHECK (balance >= 0),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Inventory: stores items players own
CREATE TABLE IF NOT EXISTS inventory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id TEXT NOT NULL,
    item_id TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(player_id, item_id)
);

-- Claimed rewards: tracks one-time rewards
CREATE TABLE IF NOT EXISTS claimed_rewards (
    player_id TEXT NOT NULL,
    reward_id TEXT NOT NULL,
    claimed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (player_id, reward_id)
);

-- Idempotency keys: prevents duplicate operations
CREATE TABLE IF NOT EXISTS idempotency_keys (
    idempotency_key TEXT PRIMARY KEY,
    player_id TEXT NOT NULL,
    operation TEXT NOT NULL,
    request_data TEXT NOT NULL,
    response_data TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL
);

-- Ledger: audit trail for all operations
CREATE TABLE IF NOT EXISTS ledger (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id TEXT NOT NULL,
    operation TEXT NOT NULL,
    amount INTEGER,
    item_id TEXT,
    reference_id TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);