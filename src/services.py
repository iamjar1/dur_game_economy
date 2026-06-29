import sqlite3
import json
import hashlib
from datetime import datetime, timedelta
from typing import Dict, Optional
from .database import get_db

def generate_idempotency_key(player_id: str, operation: str, request_data: dict) -> str:
    """Generate unique idempotency key from request."""
    data_string = f"{player_id}:{operation}:{json.dumps(request_data, sort_keys=True)}"
    return hashlib.sha256(data_string.encode()).hexdigest()

def check_idempotency(key: str) -> Optional[dict]:
    """Check if request was already processed."""
    with get_db() as conn:
        cursor = conn.execute(
            "SELECT response_data FROM idempotency_keys WHERE idempotency_key = ? AND expires_at > ?",
            (key, datetime.utcnow().isoformat())
        )
        row = cursor.fetchone()
        if row:
            return json.loads(row["response_data"])
    return None

def store_idempotency(key: str, player_id: str, operation: str, request_data: dict, response_data: dict):
    """Store idempotency key with response."""
    with get_db() as conn:
        expires_at = (datetime.utcnow() + timedelta(hours=48)).isoformat()
        conn.execute(
            "INSERT OR REPLACE INTO idempotency_keys (idempotency_key, player_id, operation, request_data, response_data, expires_at) VALUES (?, ?, ?, ?, ?, ?)",
            (key, player_id, operation, json.dumps(request_data), json.dumps(response_data), expires_at)
        )

def credit_wallet(player_id: str, amount: int, reason: str, idempotency_key: str) -> dict:
    """Credit player wallet with idempotency."""
    # Check for duplicate request
    existing = check_idempotency(idempotency_key)
    if existing:
        return existing
    
    with get_db() as conn:
        # Ensure wallet exists
        conn.execute(
            "INSERT OR IGNORE INTO wallets (player_id, balance) VALUES (?, 0)",
            (player_id,)
        )
        
        # Credit balance
        conn.execute(
            "UPDATE wallets SET balance = balance + ?, updated_at = CURRENT_TIMESTAMP WHERE player_id = ?",
            (amount, player_id)
        )
        
        # Get new balance
        cursor = conn.execute("SELECT balance FROM wallets WHERE player_id = ?", (player_id,))
        new_balance = cursor.fetchone()["balance"]
        
        # Generate transaction ID
        transaction_id = f"txn_{idempotency_key[:16]}"
        
        # Record in ledger
        conn.execute(
            "INSERT INTO ledger (player_id, operation, amount, reference_id) VALUES (?, 'credit', ?, ?)",
            (player_id, amount, transaction_id)
        )
        
        response = {
            "success": True,
            "balance": new_balance,
            "transactionId": transaction_id
        }
        
        # Store for idempotency
        store_idempotency(idempotency_key, player_id, "credit", {"amount": amount, "reason": reason}, response)
        
        return response

def purchase_item(player_id: str, item_id: str, price: int, idempotency_key: str) -> dict:
    """Purchase item with atomic debit and grant."""
    # Check for duplicate request
    existing = check_idempotency(idempotency_key)
    if existing:
        return existing
    
    with get_db() as conn:
        # Ensure wallet exists
        conn.execute(
            "INSERT OR IGNORE INTO wallets (player_id, balance) VALUES (?, 0)",
            (player_id,)
        )
        
        # Check balance (implicit lock via WAL)
        cursor = conn.execute(
            "SELECT balance FROM wallets WHERE player_id = ?",
            (player_id,)
        )
        wallet = cursor.fetchone()
        
        if not wallet:
            raise ValueError("Wallet not found")
        
        if wallet["balance"] < price:
            raise ValueError(f"Insufficient funds: balance {wallet['balance']} < price {price}")
        
        # Debit wallet
        conn.execute(
            "UPDATE wallets SET balance = balance - ?, updated_at = CURRENT_TIMESTAMP WHERE player_id = ?",
            (price, player_id)
        )
        
        # Grant item (will fail if duplicate due to UNIQUE constraint)
        try:
            conn.execute(
                "INSERT INTO inventory (player_id, item_id) VALUES (?, ?)",
                (player_id, item_id)
            )
        except sqlite3.IntegrityError:
            raise ValueError(f"Item {item_id} already owned")
        
        # Get new balance
        cursor = conn.execute("SELECT balance FROM wallets WHERE player_id = ?", (player_id,))
        new_balance = cursor.fetchone()["balance"]
        
        # Generate transaction ID
        transaction_id = f"txn_{idempotency_key[:16]}"
        
        # Record in ledger
        conn.execute(
            "INSERT INTO ledger (player_id, operation, amount, item_id, reference_id) VALUES (?, 'purchase', ?, ?, ?)",
            (player_id, price, item_id, transaction_id)
        )
        
        response = {
            "success": True,
            "balance": new_balance,
            "itemId": item_id,
            "transactionId": transaction_id
        }
        
        # Store for idempotency
        store_idempotency(idempotency_key, player_id, "purchase", {"itemId": item_id, "price": price}, response)
        
        return response

def claim_reward(player_id: str, reward_id: str, idempotency_key: str) -> dict:
    """Claim one-time reward with idempotency."""
    # Check for duplicate request
    existing = check_idempotency(idempotency_key)
    if existing:
        return existing
    
    with get_db() as conn:
        # Check if already claimed
        cursor = conn.execute(
            "SELECT 1 FROM claimed_rewards WHERE player_id = ? AND reward_id = ?",
            (player_id, reward_id)
        )
        if cursor.fetchone():
            raise ValueError(f"Reward {reward_id} already claimed")
        
        # Claim reward
        conn.execute(
            "INSERT INTO claimed_rewards (player_id, reward_id) VALUES (?, ?)",
            (player_id, reward_id)
        )
        
        # Record in ledger
        conn.execute(
            "INSERT INTO ledger (player_id, operation, reference_id) VALUES (?, 'claim', ?)",
            (player_id, reward_id)
        )
        
        response = {
            "success": True,
            "rewardId": reward_id,
            "claimedAt": datetime.utcnow().isoformat() + "Z"
        }
        
        # Store for idempotency
        store_idempotency(idempotency_key, player_id, "claim", {"rewardId": reward_id}, response)
        
        return response

def get_wallet(player_id: str) -> dict:
    """Get wallet state."""
    with get_db() as conn:
        # Get balance (default to 0 if no wallet)
        cursor = conn.execute(
            "SELECT balance FROM wallets WHERE player_id = ?",
            (player_id,)
        )
        wallet = cursor.fetchone()
        balance = wallet["balance"] if wallet else 0
        
        # Get inventory
        cursor = conn.execute(
            "SELECT item_id FROM inventory WHERE player_id = ? ORDER BY created_at",
            (player_id,)
        )
        inventory = [row["item_id"] for row in cursor.fetchall()]
        
        # Get claimed rewards
        cursor = conn.execute(
            "SELECT reward_id FROM claimed_rewards WHERE player_id = ? ORDER BY claimed_at",
            (player_id,)
        )
        claimed_rewards = [row["reward_id"] for row in cursor.fetchall()]
        
        return {
            "playerId": player_id,
            "balance": balance,
            "inventory": inventory,
            "claimedRewards": claimed_rewards
        }