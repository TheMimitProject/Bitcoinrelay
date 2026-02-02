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
    """Bitcoin network API interface using Blockstream/Mempool APIs."""
    
    def __init__(self, network: str = "testnet"):
        if network not in NETWORKS:
            raise ValueError(f"Invalid network: {network}")
        self.network = network
        self.config = NETWORKS[network]
        self.api_base = self.config["api_base"]
    
    def _get(self, endpoint: str) -> Any:
        url = f"{self.api_base}/{endpoint}"
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        return response.json()
    
    def _get_text(self, endpoint: str) -> str:
        url = f"{self.api_base}/{endpoint}"
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        return response.text
    
    def _post(self, endpoint: str, data: str) -> str:
        url = f"{self.api_base}/{endpoint}"
        response = requests.post(url, data=data, timeout=30)
        response.raise_for_status()
        return response.text
    
    def get_block_height(self) -> int:
        return int(self._get_text("blocks/tip/height"))
    
    def get_block_hash(self, height: int) -> str:
        return self._get_text(f"block-height/{height}")
    
    def get_address_utxos(self, address: str) -> List[UTXOInfo]:
        utxos = self._get(f"address/{address}/utxo")
        return [
            UTXOInfo(
                txid=u["txid"], vout=u["vout"], value_sats=u["value"],
                confirmations=u.get("status", {}).get("block_height", 0), script_pubkey=""
            ) for u in utxos
        ]
    
    def get_address_balance(self, address: str) -> Tuple[int, int]:
        """Returns (confirmed_sats, unconfirmed_sats)."""
        data = self._get(f"address/{address}")
        chain_stats = data.get("chain_stats", {})
        mempool_stats = data.get("mempool_stats", {})
        confirmed = chain_stats.get("funded_txo_sum", 0) - chain_stats.get("spent_txo_sum", 0)
        unconfirmed = mempool_stats.get("funded_txo_sum", 0) - mempool_stats.get("spent_txo_sum", 0)
        return confirmed, unconfirmed
    
    def get_transaction(self, txid: str) -> Optional[TransactionInfo]:
        try:
            tx = self._get(f"tx/{txid}")
            status = tx.get("status", {})
            return TransactionInfo(
                txid=txid, confirmed=status.get("confirmed", False),
                block_height=status.get("block_height"), fee_sats=tx.get("fee")
            )
        except requests.HTTPError as e:
            if e.response.status_code == 404:
                return None
            raise
    
    def get_address_transactions(self, address: str) -> List[Dict[str, Any]]:
        return self._get(f"address/{address}/txs")
    
    def broadcast_transaction(self, tx_hex: str) -> str:
        return self._post("tx", tx_hex)
    
    def get_fee_estimates(self) -> Dict[str, FeeEstimate]:
        try:
            url = "https://mempool.space/testnet/api/v1/fees/recommended" if self.network == "testnet" else "https://mempool.space/api/v1/fees/recommended"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            return {
                "high": FeeEstimate(data["fastestFee"], int(data["fastestFee"] * ESTIMATED_TX_VBYTES), "high"),
                "medium": FeeEstimate(data["halfHourFee"], int(data["halfHourFee"] * ESTIMATED_TX_VBYTES), "medium"),
                "low": FeeEstimate(data["hourFee"], int(data["hourFee"] * ESTIMATED_TX_VBYTES), "low"),
                "economy": FeeEstimate(data["economyFee"], int(data["economyFee"] * ESTIMATED_TX_VBYTES), "economy")
            }
        except Exception:
            default_rate = 10 if self.network == "testnet" else 20
            return {
                "high": FeeEstimate(default_rate * 2, int(default_rate * 2 * ESTIMATED_TX_VBYTES), "high"),
                "medium": FeeEstimate(default_rate, int(default_rate * ESTIMATED_TX_VBYTES), "medium"),
                "low": FeeEstimate(default_rate // 2, int(default_rate // 2 * ESTIMATED_TX_VBYTES), "low"),
                "economy": FeeEstimate(default_rate // 4, int(default_rate // 4 * ESTIMATED_TX_VBYTES), "economy")
            }


class WalletManager:
    """Manages Bitcoin wallets and key generation."""
    
    def __init__(self, network: str = "testnet"):
        self.network = network
        self.is_testnet = network == "testnet"
    
    def generate_key_pair(self) -> Tuple[str, str]:
        if self.is_testnet:
            from bit import PrivateKeyTestnet as PrivateKey
        else:
            from bit import PrivateKey
        key = PrivateKey()
        return key.segwit_address, key.to_wif()
    
    def get_key_from_wif(self, wif: str):
        if self.is_testnet:
            from bit import PrivateKeyTestnet as PrivateKey
        else:
            from bit import PrivateKey
        return PrivateKey(wif)
    
    def get_address_from_wif(self, wif: str) -> str:
        return self.get_key_from_wif(wif).segwit_address
    
    def create_transaction(self, wif: str, to_address: str, amount_sats: int, fee_sats: int, send_all: bool = False) -> Tuple[str, int]:
        key = self.get_key_from_wif(wif)
        # FIX: Convert balance to int (bit library may return string)
        balance = int(key.get_balance('satoshi'))
        
        if send_all:
            amount_sats = balance - fee_sats
        
        if amount_sats <= 0:
            raise ValueError(f"Insufficient balance. Have {balance}, need {amount_sats + fee_sats}")
        if balance < amount_sats + fee_sats:
            raise ValueError(f"Insufficient balance. Have {balance}, need {amount_sats + fee_sats}")
        
        outputs = [(to_address, amount_sats, 'satoshi')]
        tx = key.create_transaction(outputs, fee=fee_sats, absolute_fee=True)
        return tx, amount_sats
    
    def validate_address(self, address: str) -> bool:
        valid_prefixes = ('m', 'n', '2', 'tb1') if self.is_testnet else ('1', '3', 'bc1')
        if not address.startswith(valid_prefixes):
            return False
        if address.startswith(('bc1', 'tb1')):
            return 42 <= len(address) <= 62
        return 26 <= len(address) <= 35


def calculate_fibonacci_delays(num_hops: int) -> List[int]:
    if num_hops > len(FIBONACCI_DELAYS):
        fib = list(FIBONACCI_DELAYS)
        while len(fib) < num_hops:
            fib.append(fib[-1] + fib[-2])
        return fib[:num_hops]
    return FIBONACCI_DELAYS[:num_hops]


def estimate_total_fees(num_hops: int, fee_estimate: FeeEstimate) -> Dict[str, int]:
    num_transactions = num_hops + 1
    fee_per_tx = fee_estimate.estimated_fee_sats
    return {
        "fee_rate_sat_vb": fee_estimate.fee_rate_sat_vb,
        "fee_per_transaction_sats": fee_per_tx,
        "num_transactions": num_transactions,
        "total_fees_sats": fee_per_tx * num_transactions,
        "priority": fee_estimate.priority
    }


def estimate_relay_timing(num_hops: int, avg_block_time_minutes: int = 10) -> Dict[str, Any]:
    delays = calculate_fibonacci_delays(num_hops)
    total_blocks = sum(delays)
    min_time_minutes = total_blocks * avg_block_time_minutes
    return {
        "delays_per_hop": delays,
        "total_delay_blocks": total_blocks,
        "estimated_minutes": min_time_minutes,
        "estimated_hours": round(min_time_minutes / 60, 1),
        "estimated_days": round(min_time_minutes / 1440, 2)
    }
