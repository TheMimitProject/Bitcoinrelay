"""
Configuration settings for Bitcoin Relay application.
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
DATABASE_PATH = BASE_DIR / "relay.db"

# Encryption settings
SALT_LENGTH = 16
KEY_LENGTH = 32
ITERATIONS = 480000

# Bitcoin network settings
NETWORKS = {
    "testnet": {
        "name": "Bitcoin Testnet",
        "api_base": "https://blockstream.info/testnet/api",
        "explorer_base": "https://blockstream.info/testnet",
        "min_confirmations": 1,
        "dust_threshold": 546,
    },
    "mainnet": {
        "name": "Bitcoin Mainnet", 
        "api_base": "https://blockstream.info/api",
        "explorer_base": "https://blockstream.info",
        "min_confirmations": 3,
        "dust_threshold": 546,
    }
}

# Fibonacci sequence for delays (in blocks)
FIBONACCI_DELAYS = [1, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144]

# Safety limits
MAX_HOPS = 10
MIN_HOPS = 2
MAX_RELAY_AMOUNT_SATS = 10_000_000_000

# Fee estimation - average tx size for P2WPKH
ESTIMATED_TX_VBYTES = 110

# Polling interval (seconds)
BLOCK_POLL_INTERVAL = 30

# Flask settings
SECRET_KEY = os.environ.get('SECRET_KEY') or os.urandom(32)
