"""
Unit tests for Bitcoin Relay core functionality.
Run with: pytest tests/
"""
import pytest
import os
import sys
import tempfile
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from config import FIBONACCI_DELAYS, MIN_HOPS, MAX_HOPS
from encryption import KeyEncryption, generate_password_hash, verify_password_hash
from bitcoin_utils import (
    calculate_fibonacci_delays, 
    estimate_total_fees, 
    estimate_relay_timing,
    WalletManager,
    FeeEstimate
)


class TestEncryption:
    """Test encryption utilities."""
    
    def test_encrypt_decrypt(self):
        """Test basic encryption and decryption."""
        password = "testpassword123"
        secret = "L1aW4aubDFB7yfras2S1mN3bqg9nwySY8nkoLmJebSLD5BWv3ENZ"
        
        encrypted = KeyEncryption.encrypt(secret, password)
        assert encrypted != secret
        
        decrypted = KeyEncryption.decrypt(encrypted, password)
        assert decrypted == secret
    
    def test_wrong_password(self):
        """Test decryption with wrong password fails."""
        password = "testpassword123"
        wrong_password = "wrongpassword"
        secret = "testsecret"
        
        encrypted = KeyEncryption.encrypt(secret, password)
        
        with pytest.raises(Exception):
            KeyEncryption.decrypt(encrypted, wrong_password)
    
    def test_password_hash(self):
        """Test password hashing and verification."""
        password = "testpassword123"
        
        hash_value = generate_password_hash(password)
        assert hash_value is not None
        assert len(hash_value) > 0
        
        # Correct password should verify
        assert verify_password_hash(password, hash_value) is True
        
        # Wrong password should not verify
        assert verify_password_hash("wrongpassword", hash_value) is False
    
    def test_unique_encryption(self):
        """Test that same plaintext produces different ciphertext."""
        password = "testpassword123"
        secret = "testsecret"
        
        encrypted1 = KeyEncryption.encrypt(secret, password)
        encrypted2 = KeyEncryption.encrypt(secret, password)
        
        # Due to random salt/nonce, these should be different
        assert encrypted1 != encrypted2
        
        # But both should decrypt to the same value
        assert KeyEncryption.decrypt(encrypted1, password) == secret
        assert KeyEncryption.decrypt(encrypted2, password) == secret


class TestFibonacciDelays:
    """Test Fibonacci delay calculations."""
    
    def test_basic_delays(self):
        """Test basic Fibonacci delay sequence."""
        delays = calculate_fibonacci_delays(5)
        assert delays == [1, 1, 2, 3, 5]
    
    def test_longer_sequence(self):
        """Test longer Fibonacci sequence."""
        delays = calculate_fibonacci_delays(8)
        assert delays == [1, 1, 2, 3, 5, 8, 13, 21]
    
    def test_min_hops(self):
        """Test minimum number of hops."""
        delays = calculate_fibonacci_delays(MIN_HOPS)
        assert len(delays) == MIN_HOPS
    
    def test_max_hops(self):
        """Test maximum number of hops."""
        delays = calculate_fibonacci_delays(MAX_HOPS)
        assert len(delays) == MAX_HOPS
    
    def test_extended_sequence(self):
        """Test that sequence extends beyond predefined values."""
        # Request more hops than predefined
        delays = calculate_fibonacci_delays(15)
        assert len(delays) == 15
        
        # Verify it follows Fibonacci pattern
        for i in range(2, len(delays)):
            assert delays[i] == delays[i-1] + delays[i-2]


class TestFeeEstimation:
    """Test fee estimation calculations."""
    
    def test_fee_breakdown(self):
        """Test fee breakdown calculation."""
        fee_estimate = FeeEstimate(
            fee_rate_sat_vb=10.0,
            estimated_fee_sats=1100,
            priority="medium"
        )
        
        breakdown = estimate_total_fees(5, fee_estimate)
        
        assert breakdown['fee_rate_sat_vb'] == 10.0
        assert breakdown['fee_per_transaction_sats'] == 1100
        assert breakdown['num_transactions'] == 6  # 5 hops + 1 final
        assert breakdown['total_fees_sats'] == 6600
        assert breakdown['priority'] == "medium"
    
    def test_timing_estimation(self):
        """Test relay timing estimation."""
        timing = estimate_relay_timing(5)
        
        assert timing['delays_per_hop'] == [1, 1, 2, 3, 5]
        assert timing['total_delay_blocks'] == 12
        assert timing['estimated_minutes'] == 120
        assert timing['estimated_hours'] == 2.0


class TestWalletManager:
    """Test wallet management functionality."""
    
    def test_testnet_address_validation(self):
        """Test testnet address validation."""
        wallet = WalletManager("testnet")
        
        # Valid testnet addresses
        assert wallet.validate_address("tb1qw508d6qejxtdg4y5r3zarvary0c5xw7kxpjzsx") is True
        assert wallet.validate_address("2N3oefVeg6stiTb5Kh3ozCRPmWX2G7sJhQ5") is True
        assert wallet.validate_address("mipcBbFg9gMiCh81Kj8tqqdgoZub1ZJRfn") is True
        
        # Invalid - mainnet addresses on testnet
        assert wallet.validate_address("bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4") is False
        assert wallet.validate_address("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa") is False
    
    def test_mainnet_address_validation(self):
        """Test mainnet address validation."""
        wallet = WalletManager("mainnet")
        
        # Valid mainnet addresses
        assert wallet.validate_address("bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4") is True
        assert wallet.validate_address("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa") is True
        assert wallet.validate_address("3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy") is True
        
        # Invalid - testnet addresses on mainnet
        assert wallet.validate_address("tb1qw508d6qejxtdg4y5r3zarvary0c5xw7kxpjzsx") is False
        assert wallet.validate_address("mipcBbFg9gMiCh81Kj8tqqdgoZub1ZJRfn") is False


class TestConfiguration:
    """Test configuration values."""
    
    def test_hop_limits(self):
        """Test hop limits are sensible."""
        assert MIN_HOPS >= 2
        assert MAX_HOPS <= 20
        assert MIN_HOPS < MAX_HOPS
    
    def test_fibonacci_delays_defined(self):
        """Test Fibonacci delays are predefined."""
        assert len(FIBONACCI_DELAYS) >= MAX_HOPS
        
        # Verify Fibonacci pattern
        for i in range(2, len(FIBONACCI_DELAYS)):
            assert FIBONACCI_DELAYS[i] == FIBONACCI_DELAYS[i-1] + FIBONACCI_DELAYS[i-2]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
