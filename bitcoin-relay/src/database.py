"""
Database module for persistent storage of relay chains and keys.
Uses SQLite for reliable, file-based storage.
"""
import sqlite3
from typing import Optional, List, Dict, Any
from contextlib import contextmanager
from pathlib import Path

from .config import DATABASE_PATH


def get_db_path() -> Path:
    return DATABASE_PATH


@contextmanager
def get_connection():
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_database():
    with get_connection() as conn:
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS relay_chains (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                network TEXT NOT NULL CHECK (network IN ('testnet', 'mainnet')),
                status TEXT NOT NULL DEFAULT 'pending' 
                    CHECK (status IN ('pending', 'active', 'completed', 'failed', 'cancelled')),
                intake_address TEXT NOT NULL,
                intake_privkey_encrypted TEXT NOT NULL,
                final_address TEXT NOT NULL,
                final_is_generated INTEGER NOT NULL DEFAULT 0,
                final_privkey_encrypted TEXT,
                total_hops INTEGER NOT NULL,
                current_hop INTEGER NOT NULL DEFAULT 0,
                amount_received_sats INTEGER,
                amount_sent_sats INTEGER,
                total_fees_sats INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                started_at TIMESTAMP,
                completed_at TIMESTAMP,
                error_message TEXT
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS relay_hops (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chain_id INTEGER NOT NULL REFERENCES relay_chains(id) ON DELETE CASCADE,
                hop_number INTEGER NOT NULL,
                address TEXT NOT NULL,
                privkey_encrypted TEXT NOT NULL,
                delay_blocks INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'waiting'
                    CHECK (status IN ('waiting', 'funded', 'pending_relay', 'relayed', 'failed')),
                incoming_txid TEXT,
                incoming_amount_sats INTEGER,
                incoming_confirmed_at_block INTEGER,
                outgoing_txid TEXT,
                outgoing_amount_sats INTEGER,
                outgoing_fee_sats INTEGER,
                relay_at_block INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                funded_at TIMESTAMP,
                relayed_at TIMESTAMP,
                UNIQUE(chain_id, hop_number)
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS transaction_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chain_id INTEGER NOT NULL REFERENCES relay_chains(id) ON DELETE CASCADE,
                hop_id INTEGER REFERENCES relay_hops(id) ON DELETE CASCADE,
                event_type TEXT NOT NULL,
                txid TEXT,
                amount_sats INTEGER,
                fee_sats INTEGER,
                block_height INTEGER,
                details TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS block_tracker (
                network TEXT PRIMARY KEY,
                last_height INTEGER NOT NULL,
                last_hash TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_chains_status ON relay_chains(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_chains_network ON relay_chains(network)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_hops_chain ON relay_hops(chain_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_hops_status ON relay_hops(status)")


# Settings Operations
def get_setting(key: str) -> Optional[str]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = cursor.fetchone()
        return row['value'] if row else None


def set_setting(key: str, value: str):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO settings (key, value, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(key) DO UPDATE SET value = ?, updated_at = CURRENT_TIMESTAMP
        """, (key, value, value))


def get_master_password_hash() -> Optional[str]:
    return get_setting('master_password_hash')


def set_master_password_hash(hash_value: str):
    set_setting('master_password_hash', hash_value)


def get_active_network() -> str:
    return get_setting('active_network') or 'testnet'


def set_active_network(network: str):
    if network not in ('testnet', 'mainnet'):
        raise ValueError("Network must be 'testnet' or 'mainnet'")
    set_setting('active_network', network)


# Relay Chain Operations
def create_relay_chain(name: str, network: str, intake_address: str, intake_privkey_encrypted: str,
                       final_address: str, final_is_generated: bool, final_privkey_encrypted: Optional[str],
                       total_hops: int) -> int:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO relay_chains (name, network, intake_address, intake_privkey_encrypted,
                final_address, final_is_generated, final_privkey_encrypted, total_hops)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (name, network, intake_address, intake_privkey_encrypted, final_address,
              int(final_is_generated), final_privkey_encrypted, total_hops))
        return cursor.lastrowid


def get_relay_chain(chain_id: int) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM relay_chains WHERE id = ?", (chain_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def get_all_relay_chains(network: Optional[str] = None) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        if network:
            cursor.execute("SELECT * FROM relay_chains WHERE network = ? ORDER BY created_at DESC", (network,))
        else:
            cursor.execute("SELECT * FROM relay_chains ORDER BY created_at DESC")
        return [dict(row) for row in cursor.fetchall()]


def update_chain_status(chain_id: int, status: str, error_message: Optional[str] = None):
    with get_connection() as conn:
        cursor = conn.cursor()
        updates = ["status = ?"]
        params = [status]
        if status == 'active':
            updates.append("started_at = CURRENT_TIMESTAMP")
        elif status in ('completed', 'failed', 'cancelled'):
            updates.append("completed_at = CURRENT_TIMESTAMP")
        if error_message:
            updates.append("error_message = ?")
            params.append(error_message)
        params.append(chain_id)
        cursor.execute(f"UPDATE relay_chains SET {', '.join(updates)} WHERE id = ?", params)


def update_chain_amounts(chain_id: int, amount_received_sats: Optional[int] = None,
                         amount_sent_sats: Optional[int] = None, total_fees_sats: Optional[int] = None,
                         current_hop: Optional[int] = None):
    with get_connection() as conn:
        cursor = conn.cursor()
        updates, params = [], []
        if amount_received_sats is not None:
            updates.append("amount_received_sats = ?")
            params.append(amount_received_sats)
        if amount_sent_sats is not None:
            updates.append("amount_sent_sats = ?")
            params.append(amount_sent_sats)
        if total_fees_sats is not None:
            updates.append("total_fees_sats = ?")
            params.append(total_fees_sats)
        if current_hop is not None:
            updates.append("current_hop = ?")
            params.append(current_hop)
        if updates:
            params.append(chain_id)
            cursor.execute(f"UPDATE relay_chains SET {', '.join(updates)} WHERE id = ?", params)


# Relay Hop Operations
def create_relay_hop(chain_id: int, hop_number: int, address: str, privkey_encrypted: str, delay_blocks: int) -> int:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO relay_hops (chain_id, hop_number, address, privkey_encrypted, delay_blocks)
            VALUES (?, ?, ?, ?, ?)
        """, (chain_id, hop_number, address, privkey_encrypted, delay_blocks))
        return cursor.lastrowid


def get_relay_hops(chain_id: int) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM relay_hops WHERE chain_id = ? ORDER BY hop_number ASC", (chain_id,))
        return [dict(row) for row in cursor.fetchall()]


def update_hop_funded(hop_id: int, incoming_txid: str, incoming_amount_sats: int,
                      confirmed_at_block: int, relay_at_block: int):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE relay_hops SET status = 'pending_relay', incoming_txid = ?, incoming_amount_sats = ?,
                incoming_confirmed_at_block = ?, relay_at_block = ?, funded_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (incoming_txid, incoming_amount_sats, confirmed_at_block, relay_at_block, hop_id))


def update_hop_relayed(hop_id: int, outgoing_txid: str, outgoing_amount_sats: int, outgoing_fee_sats: int):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE relay_hops SET status = 'relayed', outgoing_txid = ?, outgoing_amount_sats = ?,
                outgoing_fee_sats = ?, relayed_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (outgoing_txid, outgoing_amount_sats, outgoing_fee_sats, hop_id))


def update_hop_status(hop_id: int, status: str):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE relay_hops SET status = ? WHERE id = ?", (status, hop_id))


# Transaction Log
def log_transaction(chain_id: int, event_type: str, hop_id: Optional[int] = None, txid: Optional[str] = None,
                    amount_sats: Optional[int] = None, fee_sats: Optional[int] = None,
                    block_height: Optional[int] = None, details: Optional[str] = None):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO transaction_log (chain_id, hop_id, event_type, txid, amount_sats, fee_sats, block_height, details)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (chain_id, hop_id, event_type, txid, amount_sats, fee_sats, block_height, details))


def get_transaction_log(chain_id: int) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM transaction_log WHERE chain_id = ? ORDER BY created_at ASC", (chain_id,))
        return [dict(row) for row in cursor.fetchall()]


# Block Tracker
def get_last_block_height(network: str) -> Optional[int]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT last_height FROM block_tracker WHERE network = ?", (network,))
        row = cursor.fetchone()
        return row['last_height'] if row else None


def update_block_height(network: str, height: int, block_hash: Optional[str] = None):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO block_tracker (network, last_height, last_hash, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(network) DO UPDATE SET last_height = ?, last_hash = ?, updated_at = CURRENT_TIMESTAMP
        """, (network, height, block_hash, height, block_hash))
