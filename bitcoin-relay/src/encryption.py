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
    """Handles encryption and decryption of private keys using AES-256-GCM."""
    
    @staticmethod
    def derive_key(password: str, salt: bytes) -> bytes:
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
        try:
            salt = os.urandom(SALT_LENGTH)
            nonce = os.urandom(12)
            key = KeyEncryption.derive_key(password, salt)
            aesgcm = AESGCM(key)
            ciphertext = aesgcm.encrypt(nonce, plaintext.encode('utf-8'), None)
            encrypted_data = salt + nonce + ciphertext
            return base64.b64encode(encrypted_data).decode('utf-8')
        except Exception as e:
            raise EncryptionError(f"Encryption failed: {str(e)}")
    
    @staticmethod
    def decrypt(encrypted_data: str, password: str) -> str:
        try:
            data = base64.b64decode(encrypted_data)
            salt = data[:SALT_LENGTH]
            nonce = data[SALT_LENGTH:SALT_LENGTH + 12]
            ciphertext = data[SALT_LENGTH + 12:]
            key = KeyEncryption.derive_key(password, salt)
            aesgcm = AESGCM(key)
            plaintext = aesgcm.decrypt(nonce, ciphertext, None)
            return plaintext.decode('utf-8')
        except Exception:
            raise EncryptionError("Decryption failed - wrong password or corrupted data")
    
    @staticmethod
    def verify_password(encrypted_data: str, password: str) -> bool:
        try:
            KeyEncryption.decrypt(encrypted_data, password)
            return True
        except EncryptionError:
            return False


def generate_password_hash(password: str) -> str:
    salt = os.urandom(SALT_LENGTH)
    key = KeyEncryption.derive_key(password, salt)
    hash_value = hashlib.sha256(key).digest()
    return base64.b64encode(salt + hash_value).decode('utf-8')


def verify_password_hash(password: str, stored_hash: str) -> bool:
    try:
        data = base64.b64decode(stored_hash)
        salt = data[:SALT_LENGTH]
        stored_hash_value = data[SALT_LENGTH:]
        key = KeyEncryption.derive_key(password, salt)
        computed_hash = hashlib.sha256(key).digest()
        return computed_hash == stored_hash_value
    except Exception:
        return False
