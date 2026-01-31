"""
Bitcoin utilities for wallet generation, transaction creation, and network interaction.
Uses the 'bit' library for Bitcoin operations.
"""
import requests
from typing import Optional, Tuple, List, Dict, Any
from dataclasses import dataclass
from enum import Enum

from .config import NETWORKS, ESTIMATED_TX_VBYTES, FIBONACCI_DELAYS, MAX_HOPS


class NetworkType(Enum):
    TESTNET = "testnet"
    MAINNET = "mainnet"


@dataclass
class FeeEstimate:
    """Fee estimation result."""
    fee_rate_sat_vb: float
    estimated_fee_sats: int
    priority: str


@dataclass
class UTXOInfo:
    """Unspent transaction output information."""
    txid: str
    vout: int
    value_sats: int
    confirmations: int
    script_pubkey: str


@dataclass
class TransactionInfo:
    """Transaction information."""
    txid: str
    confirmed: bool
    block_height: Optional[int]
    fee_sats: Optional[int]


class BitcoinAPI:
    """
    Bitcoin network API interface using Blockstream/Mempool APIs.
    Handles both testnet and mainnet.
    """
    
    def __init__(self, network: str = "testnet"):
        if network not in NETWORKS:
            raise ValueError(f"Invalid network: {network}")
        self.network = network
        self.config = NETWORKS[network]
        self.api_base = self.config["api_base"]
    
    def _get(self, endpoint: str) -> Any:
        """Make a GET request to the API."""
        url = f"{self.api_base}/{endpoint}"
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        return response.json()
    
    def _get_text(self, endpoint: str) -> str:
        """Make a GET request expecting text response."""
        url = f"{self.api_base}/{endpoint}"
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        return response.text
    
    def _post(self, endpoint: str, data: str) -> str:
        """Make a POST request."""
        url = f"{self.api_base}/{endpoint}"
        response = requests.post(url, data=data, timeout=30)
        response.raise_for_status()
        return response.text
    
    def get_block_height(self) -> int:
        """Get the current block height."""
        return int(self._get_text("blocks/tip/height"))
    
    def get_block_hash(self, height: int) -> str:
        """Get the block hash at a given height."""
        return self._get_text(f"block-height/{height}")
    
    def get_address_utxos(self, address: str) -> List[UTXOInfo]:
        """Get unspent transaction outputs for an address."""
        utxos = self._get(f"address/{address}/utxo")
        return [
            UTXOInfo(
                txid=u["txid"],
                vout=u["vout"],
                value_sats=u["value"],
                confirmations=u.get("status", {}).get("block_height", 0),
                script_pubkey=""  # Not always provided
            )
            for u in utxos
        ]
    
    def get_address_balance(self, address: str) -> Tuple[int, int]:
        """
        Get the balance of an address.
        Returns (confirmed_sats, unconfirmed_sats).
        """
        data = self._get(f"address/{address}")
        chain_stats = data.get("chain_stats", {})
        mempool_stats = data.get("mempool_stats", {})
        
        confirmed = chain_stats.get("funded_txo_sum", 0) - chain_stats.get("spent_txo_sum", 0)
        unconfirmed = mempool_stats.get("funded_txo_sum", 0) - mempool_stats.get("spent_txo_sum", 0)
        
        return confirmed, unconfirmed
    
    def get_transaction(self, txid: str) -> Optional[TransactionInfo]:
        """Get transaction details."""
        try:
            tx = self._get(f"tx/{txid}")
            status = tx.get("status", {})
            return TransactionInfo(
                txid=txid,
                confirmed=status.get("confirmed", False),
                block_height=status.get("block_height"),
                fee_sats=tx.get("fee")
            )
        except requests.HTTPError as e:
            if e.response.status_code == 404:
                return None
            raise
    
    def get_address_transactions(self, address: str) -> List[Dict[str, Any]]:
        """Get transactions for an address."""
        return self._get(f"address/{address}/txs")
    
    def broadcast_transaction(self, tx_hex: str) -> str:
        """
        Broadcast a signed transaction to the network.
        Returns the transaction ID.
        """
        return self._post("tx", tx_hex)
    
    def get_fee_estimates(self) -> Dict[str, FeeEstimate]:
        """
        Get current fee estimates.
        Uses mempool.space API for better estimates.
        """
        # Try mempool.space first for better estimates
        try:
            if self.network == "testnet":
                url = "https://mempool.space/testnet/api/v1/fees/recommended"
            else:
                url = "https://mempool.space/api/v1/fees/recommended"
            
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            return {
                "high": FeeEstimate(
                    fee_rate_sat_vb=data["fastestFee"],
                    estimated_fee_sats=int(data["fastestFee"] * ESTIMATED_TX_VBYTES),
                    priority="high"
                ),
                "medium": FeeEstimate(
                    fee_rate_sat_vb=data["halfHourFee"],
                    estimated_fee_sats=int(data["halfHourFee"] * ESTIMATED_TX_VBYTES),
                    priority="medium"
                ),
                "low": FeeEstimate(
                    fee_rate_sat_vb=data["hourFee"],
                    estimated_fee_sats=int(data["hourFee"] * ESTIMATED_TX_VBYTES),
                    priority="low"
                ),
                "economy": FeeEstimate(
                    fee_rate_sat_vb=data["economyFee"],
                    estimated_fee_sats=int(data["economyFee"] * ESTIMATED_TX_VBYTES),
                    priority="economy"
                )
            }
        except Exception:
            # Fallback to reasonable defaults
            default_rate = 10 if self.network == "testnet" else 20
            return {
                "high": FeeEstimate(default_rate * 2, int(default_rate * 2 * ESTIMATED_TX_VBYTES), "high"),
                "medium": FeeEstimate(default_rate, int(default_rate * ESTIMATED_TX_VBYTES), "medium"),
                "low": FeeEstimate(default_rate // 2, int(default_rate // 2 * ESTIMATED_TX_VBYTES), "low"),
                "economy": FeeEstimate(default_rate // 4, int(default_rate // 4 * ESTIMATED_TX_VBYTES), "economy")
            }


class WalletManager:
    """
    Manages Bitcoin wallets and key generation.
    Uses the 'bit' library for key operations.
    """
    
    def __init__(self, network: str = "testnet"):
        self.network = network
        self.is_testnet = network == "testnet"
    
    def generate_key_pair(self) -> Tuple[str, str]:
        """
        Generate a new key pair.
        Returns (address, private_key_wif).
        """
        # Import here to allow the module to load even without bit installed
        if self.is_testnet:
            from bit import PrivateKeyTestnet as PrivateKey
        else:
            from bit import PrivateKey
        
        key = PrivateKey()
        return key.segwit_address, key.to_wif()
    
    def get_key_from_wif(self, wif: str):
        """
        Load a private key from WIF format.
        Returns a bit PrivateKey object.
        """
        if self.is_testnet:
            from bit import PrivateKeyTestnet as PrivateKey
        else:
            from bit import PrivateKey
        
        return PrivateKey(wif)
    
    def get_address_from_wif(self, wif: str) -> str:
        """Get the segwit address for a WIF private key."""
        key = self.get_key_from_wif(wif)
        return key.segwit_address
    
    def create_transaction(
        self,
        wif: str,
        to_address: str,
        amount_sats: int,
        fee_sats: int,
        send_all: bool = False
    ) -> Tuple[str, int]:
        """
        Create and sign a transaction.
        
        Args:
            wif: Private key in WIF format
            to_address: Destination address
            amount_sats: Amount to send in satoshis (ignored if send_all=True)
            fee_sats: Transaction fee in satoshis
            send_all: If True, send entire balance minus fee
        
        Returns:
            Tuple of (signed_tx_hex, actual_amount_sent_sats)
        """
        key = self.get_key_from_wif(wif)
        
        # Get current balance
        balance = key.get_balance('satoshi')
        
        if send_all:
            amount_sats = balance - fee_sats
        
        if amount_sats <= 0:
            raise ValueError(f"Insufficient balance. Have {balance}, need {amount_sats + fee_sats}")
        
        if balance < amount_sats + fee_sats:
            raise ValueError(f"Insufficient balance. Have {balance}, need {amount_sats + fee_sats}")
        
        # Create transaction
        outputs = [(to_address, amount_sats, 'satoshi')]
        tx = key.create_transaction(outputs, fee=fee_sats, absolute_fee=True)
        
        return tx, amount_sats
    
    def validate_address(self, address: str) -> bool:
        """Validate a Bitcoin address."""
        # Basic validation - check format
        if self.is_testnet:
            # Testnet addresses start with m, n, 2, or tb1
            valid_prefixes = ('m', 'n', '2', 'tb1')
        else:
            # Mainnet addresses start with 1, 3, or bc1
            valid_prefixes = ('1', '3', 'bc1')
        
        if not address.startswith(valid_prefixes):
            return False
        
        # Check length
        if address.startswith(('bc1', 'tb1')):
            # Bech32 address
            return 42 <= len(address) <= 62
        else:
            # Legacy or P2SH address
            return 26 <= len(address) <= 35


def calculate_fibonacci_delays(num_hops: int) -> List[int]:
    """
    Calculate Fibonacci-paced delays for each hop.
    
    Args:
        num_hops: Number of intermediate hops
        
    Returns:
        List of block delays for each hop
    """
    if num_hops > len(FIBONACCI_DELAYS):
        # Extend Fibonacci sequence if needed
        fib = list(FIBONACCI_DELAYS)
        while len(fib) < num_hops:
            fib.append(fib[-1] + fib[-2])
        return fib[:num_hops]
    return FIBONACCI_DELAYS[:num_hops]


def estimate_total_fees(
    num_hops: int,
    fee_estimate: FeeEstimate
) -> Dict[str, int]:
    """
    Estimate total fees for a relay chain.
    
    Args:
        num_hops: Number of intermediate hops
        fee_estimate: Fee estimate to use
        
    Returns:
        Dictionary with fee breakdown
    """
    # Each hop creates one transaction
    # Total transactions = num_hops + 1 (including final relay to destination)
    num_transactions = num_hops + 1
    
    fee_per_tx = fee_estimate.estimated_fee_sats
    total_fees = fee_per_tx * num_transactions
    
    return {
        "fee_rate_sat_vb": fee_estimate.fee_rate_sat_vb,
        "fee_per_transaction_sats": fee_per_tx,
        "num_transactions": num_transactions,
        "total_fees_sats": total_fees,
        "priority": fee_estimate.priority
    }


def estimate_relay_timing(num_hops: int, avg_block_time_minutes: int = 10) -> Dict[str, Any]:
    """
    Estimate timing for a relay chain based on Fibonacci delays.
    
    Args:
        num_hops: Number of intermediate hops
        avg_block_time_minutes: Average block time (default 10 for Bitcoin)
        
    Returns:
        Dictionary with timing estimates
    """
    delays = calculate_fibonacci_delays(num_hops)
    total_blocks = sum(delays)
    
    # Estimate times
    min_time_minutes = total_blocks * avg_block_time_minutes
    
    return {
        "delays_per_hop": delays,
        "total_delay_blocks": total_blocks,
        "estimated_minutes": min_time_minutes,
        "estimated_hours": round(min_time_minutes / 60, 1),
        "estimated_days": round(min_time_minutes / 1440, 2)
    }
