import os
import sys
import base64
from cryptography.fernet import Fernet

ENCRYPTION_KEY_ENV = "ENCRYPTION_KEY"

_fernet: Fernet = None


def _load_or_generate_key() -> bytes:
    key_str = os.getenv(ENCRYPTION_KEY_ENV)
    if key_str:
        return base64.urlsafe_b64decode(key_str)

    key = Fernet.generate_key()
    key_b64 = base64.urlsafe_b64encode(key).decode()
    print(f"\n{'='*60}")
    print("IMPORTANT: Encryption key generated!")
    print(f"Add this to your .env file to persist across restarts:")
    print(f"\nENCRYPTION_KEY={key_b64}")
    print(f"{'='*60}\n")
    return key


def get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        _fernet = Fernet(_load_or_generate_key())
    return _fernet


def encrypt_token(token: str) -> str:
    fernet = get_fernet()
    return fernet.encrypt(token.encode()).decode()


def decrypt_token(encrypted: str) -> str:
    fernet = get_fernet()
    return fernet.decrypt(encrypted.encode()).decode()


def generate_key() -> str:
    key = Fernet.generate_key()
    return base64.urlsafe_b64encode(key).decode()