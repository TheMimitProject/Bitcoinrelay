"""
Encryption utilities for secure key storage.
Uses AES-256-GCM with PBKDF2 key derivation.
"""
import os
import base64
import hashlib
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend

from .config import SALT_LENGTH, KEY_LENGTH, ITERATIONS


class EncryptionError(Exception):
    """Raised when encryption/decryption fails."""
    pass


class KeyEncryption:
    """
    Handles encryption and decryption of private keys.
    Uses AES-256-GCM for authenticated encryption.
    """
    
    @staticmethod
    def derive_key(password: str, salt: bytes) -> bytes:
        """
        Derive an encryption key from password using PBKDF2.
        
        Args:
            password: User's encryption password
            salt: Random salt for key derivation
            
        Returns:
            32-byte derived key
        """
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=KEY_LENGTH,
            salt=salt,
            iterations=ITERATIONS,
            backend=default_backend()
        )
        return kdf.derive(password.encode('utf-8'))
    
    @staticmethod
    def encrypt(plaintext: str, password: str) -> str:
        """
        Encrypt a private key with a password.
        
        Args:
            plaintext: The private key (WIF format)
            password: User's encryption password
            
        Returns:
            Base64-encoded encrypted data (salt + nonce + ciphertext)
        """
        try:
            # Generate random salt and nonce
            salt = os.urandom(SALT_LENGTH)
            nonce = os.urandom(12)  # 96 bits for GCM
            
            # Derive key from password
            key = KeyEncryption.derive_key(password, salt)
            
            # Encrypt using AES-GCM
            aesgcm = AESGCM(key)
            ciphertext = aesgcm.encrypt(nonce, plaintext.encode('utf-8'), None)
            
            # Combine salt + nonce + ciphertext
            encrypted_data = salt + nonce + ciphertext
            
            return base64.b64encode(encrypted_data).decode('utf-8')
            
        except Exception as e:
            raise EncryptionError(f"Encryption failed: {str(e)}")
    
    @staticmethod
    def decrypt(encrypted_data: str, password: str) -> str:
        """
        Decrypt a private key with a password.
        
        Args:
            encrypted_data: Base64-encoded encrypted data
            password: User's encryption password
            
        Returns:
            The decrypted private key (WIF format)
            
        Raises:
            EncryptionError: If decryption fails (wrong password or corrupted data)
        """
        try:
            # Decode from base64
            data = base64.b64decode(encrypted_data)
            
            # Extract components
            salt = data[:SALT_LENGTH]
            nonce = data[SALT_LENGTH:SALT_LENGTH + 12]
            ciphertext = data[SALT_LENGTH + 12:]
            
            # Derive key from password
            key = KeyEncryption.derive_key(password, salt)
            
            # Decrypt using AES-GCM
            aesgcm = AESGCM(key)
            plaintext = aesgcm.decrypt(nonce, ciphertext, None)
            
            return plaintext.decode('utf-8')
            
        except Exception as e:
            raise EncryptionError(f"Decryption failed - wrong password or corrupted data")
    
    @staticmethod
    def verify_password(encrypted_data: str, password: str) -> bool:
        """
        Verify if a password can decrypt the data.
        
        Args:
            encrypted_data: Base64-encoded encrypted data
            password: Password to verify
            
        Returns:
            True if password is correct, False otherwise
        """
        try:
            KeyEncryption.decrypt(encrypted_data, password)
            return True
        except EncryptionError:
            return False


def generate_password_hash(password: str) -> str:
    """
    Generate a hash of the master password for verification.
    This is stored separately to verify the password without decrypting keys.
    """
    salt = os.urandom(SALT_LENGTH)
    key = KeyEncryption.derive_key(password, salt)
    hash_value = hashlib.sha256(key).digest()
    return base64.b64encode(salt + hash_value).decode('utf-8')


def verify_password_hash(password: str, stored_hash: str) -> bool:
    """
    Verify a password against a stored hash.
    """
    try:
        data = base64.b64decode(stored_hash)
        salt = data[:SALT_LENGTH]
        stored_hash_value = data[SALT_LENGTH:]
        
        key = KeyEncryption.derive_key(password, salt)
        computed_hash = hashlib.sha256(key).digest()
        
        # Constant-time comparison
        return computed_hash == stored_hash_value
    except Exception:
        return False
