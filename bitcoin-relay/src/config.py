"""
Configuration settings for Bitcoin Relay application.
"""
import os
from pathlib import Path

# Base directory
BASE_DIR = Path(__file__).parent.parent

# Database
DATABASE_PATH = BASE_DIR / "relay.db"

# Encryption settings
SALT_LENGTH = 16
KEY_LENGTH = 32
ITERATIONS = 480000  # OWASP recommended for PBKDF2-SHA256

# Bitcoin network settings
NETWORKS = {
    "testnet": {
        "name": "Bitcoin Testnet",
        "api_base": "https://blockstream.info/testnet/api",
        "explorer_base": "https://blockstream.info/testnet",
        "min_confirmations": 1,
        "dust_threshold": 546,  # satoshis
    },
    "mainnet": {
        "name": "Bitcoin Mainnet", 
        "api_base": "https://blockstream.info/api",
        "explorer_base": "https://blockstream.info",
        "min_confirmations": 3,
        "dust_threshold": 546,  # satoshis
    }
}

# Fibonacci sequence for delays (in blocks)
# Each hop waits this many blocks before relaying
FIBONACCI_DELAYS = [1, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144]

# Safety limits
MAX_HOPS = 10
MIN_HOPS = 2
MAX_RELAY_AMOUNT_SATS = 10_000_000_000  # 100 BTC safety limit

# Fee estimation
FEE_RATES = {
    "low": "hourFee",      # ~1 hour confirmation
    "medium": "halfHourFee",  # ~30 min confirmation
    "high": "fastestFee",  # Next block
}

# Average transaction size for P2WPKH (native segwit)
# 1 input, 1 output (send all)
ESTIMATED_TX_VBYTES = 110

# Polling interval for block monitoring (seconds)
BLOCK_POLL_INTERVAL = 60

# Flask settings
SECRET_KEY = os.environ.get('SECRET_KEY') or os.urandom(32)
