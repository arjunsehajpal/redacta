import os
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class LocalKMS:
    """Local symmetric key manager using AES-GCM encryption.

    This class handles generation, loading, and usage of a local symmetric
    encryption key for protecting PII data.
    """

    def __init__(self, key_path: Path | str):
        """Initialize LocalKMS with a key path.

        Args:
            key_path: Path to the key file. If it doesn't exist, a new key
                     will be generated and saved there.
        """
        self.key_path = Path(key_path)
        self._key = self._load_or_generate_key()
        self._cipher = AESGCM(self._key)

    def _load_or_generate_key(self) -> bytes:
        """Load existing key or generate a new one.

        Returns:
            32-byte encryption key
        """
        if self.key_path.exists():
            with open(self.key_path, "rb") as f:
                key = f.read()
                if len(key) != 32:
                    raise ValueError(f"Invalid key length in {self.key_path}")
                return key
        else:
            key = AESGCM.generate_key(bit_length=256)
            self.key_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.key_path, "wb") as f:
                f.write(key)
            self.key_path.chmod(0o600)
            return key

    def encrypt(self, plaintext: bytes) -> bytes:
        """Encrypt plaintext using AES-GCM.

        Args:
            plaintext: Data to encrypt

        Returns:
            Encrypted data (nonce + ciphertext)
        """
        nonce = os.urandom(12)
        ciphertext = self._cipher.encrypt(nonce, plaintext, None)
        return nonce + ciphertext

    def decrypt(self, ciphertext: bytes) -> bytes:
        """Decrypt ciphertext using AES-GCM.

        Args:
            ciphertext: Encrypted data (nonce + ciphertext)

        Returns:
            Decrypted plaintext

        Raises:
            cryptography.exceptions.InvalidTag: If decryption fails
        """
        nonce = ciphertext[:12]
        encrypted_data = ciphertext[12:]
        return self._cipher.decrypt(nonce, encrypted_data, None)
