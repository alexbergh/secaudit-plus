"""Encryption utilities для SecAudit+."""

import gnupg
import os
from pathlib import Path
from typing import Optional, List, Union
from dataclasses import dataclass


class EncryptionError(Exception):
    """Encryption/Decryption error."""
    pass


@dataclass
class EncryptionResult:
    """Result of encryption operation."""
    success: bool
    encrypted_data: Optional[bytes] = None
    output_file: Optional[Path] = None
    fingerprint: Optional[str] = None
    error: Optional[str] = None


@dataclass
class DecryptionResult:
    """Result of decryption operation."""
    success: bool
    decrypted_data: Optional[bytes] = None
    output_file: Optional[Path] = None
    fingerprint: Optional[str] = None
    error: Optional[str] = None


class GPGEncryption:
    """
    GPG encryption for reports and sensitive data.
    
    Supports:
    - File encryption/decryption
    - String encryption/decryption
    - Multiple recipients
    - Signature verification
    """
    
    def __init__(self, gnupghome: Optional[Path] = None):
        """
        Initialize GPG encryption.
        
        Args:
            gnupghome: Path to GPG home directory (default: ~/.gnupg)
        """
        if gnupghome:
            self.gnupghome = str(gnupghome)
        else:
            self.gnupghome = str(Path.home() / ".gnupg")
        
        self.gpg = gnupg.GPG(gnupghome=self.gnupghome)
    
    def list_keys(self, secret: bool = False) -> List[dict]:
        """
        List available GPG keys.
        
        Args:
            secret: List secret keys instead of public keys
            
        Returns:
            List of key dictionaries
        """
        keys = self.gpg.list_keys(secret=secret)
        return keys
    
    def import_key(self, key_data: Union[str, bytes]) -> dict:
        """
        Import a GPG key.
        
        Args:
            key_data: Key data (ASCII armored or binary)
            
        Returns:
            Import result dictionary
        """
        if isinstance(key_data, str):
            key_data = key_data.encode()
        
        result = self.gpg.import_keys(key_data)
        return {
            "count": result.count,
            "fingerprints": result.fingerprints,
            "results": result.results
        }
    
    def export_key(self, keyid: str, secret: bool = False) -> str:
        """
        Export a GPG key.
        
        Args:
            keyid: Key ID or fingerprint
            secret: Export secret key instead of public key
            
        Returns:
            ASCII armored key
        """
        return self.gpg.export_keys(keyid, secret=secret)
    
    def encrypt_file(
        self,
        input_file: Path,
        output_file: Optional[Path] = None,
        recipients: Optional[List[str]] = None,
        sign: bool = False,
        armor: bool = True,
    ) -> EncryptionResult:
        """
        Encrypt a file with GPG.
        
        Args:
            input_file: Path to file to encrypt
            output_file: Path to output file (default: input_file.gpg)
            recipients: List of recipient key IDs/emails
            sign: Also sign the file
            armor: Use ASCII armor format
            
        Returns:
            EncryptionResult
        """
        if not input_file.exists():
            return EncryptionResult(
                success=False,
                error=f"Input file not found: {input_file}"
            )
        
        if output_file is None:
            output_file = input_file.with_suffix(input_file.suffix + ".gpg")
        
        try:
            with open(input_file, 'rb') as f:
                result = self.gpg.encrypt_file(
                    f,
                    recipients=recipients,
                    output=str(output_file),
                    sign=sign,
                    armor=armor,
                    always_trust=True
                )
            
            if result.ok:
                return EncryptionResult(
                    success=True,
                    output_file=output_file,
                    fingerprint=result.fingerprint
                )
            else:
                return EncryptionResult(
                    success=False,
                    error=result.status
                )
        
        except Exception as e:
            return EncryptionResult(
                success=False,
                error=str(e)
            )
    
    def decrypt_file(
        self,
        input_file: Path,
        output_file: Optional[Path] = None,
        passphrase: Optional[str] = None,
    ) -> DecryptionResult:
        """
        Decrypt a GPG encrypted file.
        
        Args:
            input_file: Path to encrypted file
            output_file: Path to output file (default: remove .gpg extension)
            passphrase: Passphrase for private key
            
        Returns:
            DecryptionResult
        """
        if not input_file.exists():
            return DecryptionResult(
                success=False,
                error=f"Input file not found: {input_file}"
            )
        
        if output_file is None:
            if input_file.suffix == ".gpg":
                output_file = input_file.with_suffix("")
            else:
                output_file = input_file.with_suffix(".decrypted")
        
        try:
            with open(input_file, 'rb') as f:
                result = self.gpg.decrypt_file(
                    f,
                    output=str(output_file),
                    passphrase=passphrase,
                    always_trust=True
                )
            
            if result.ok:
                return DecryptionResult(
                    success=True,
                    output_file=output_file,
                    fingerprint=result.fingerprint
                )
            else:
                return DecryptionResult(
                    success=False,
                    error=result.status
                )
        
        except Exception as e:
            return DecryptionResult(
                success=False,
                error=str(e)
            )
    
    def encrypt_string(
        self,
        data: str,
        recipients: Optional[List[str]] = None,
        sign: bool = False,
    ) -> EncryptionResult:
        """
        Encrypt a string with GPG.
        
        Args:
            data: String to encrypt
            recipients: List of recipient key IDs/emails
            sign: Also sign the data
            
        Returns:
            EncryptionResult with encrypted_data
        """
        try:
            result = self.gpg.encrypt(
                data,
                recipients=recipients,
                sign=sign,
                always_trust=True
            )
            
            if result.ok:
                return EncryptionResult(
                    success=True,
                    encrypted_data=str(result).encode(),
                    fingerprint=result.fingerprint
                )
            else:
                return EncryptionResult(
                    success=False,
                    error=result.status
                )
        
        except Exception as e:
            return EncryptionResult(
                success=False,
                error=str(e)
            )
    
    def decrypt_string(
        self,
        encrypted_data: Union[str, bytes],
        passphrase: Optional[str] = None,
    ) -> DecryptionResult:
        """
        Decrypt a GPG encrypted string.
        
        Args:
            encrypted_data: Encrypted data
            passphrase: Passphrase for private key
            
        Returns:
            DecryptionResult with decrypted_data
        """
        try:
            result = self.gpg.decrypt(
                encrypted_data,
                passphrase=passphrase,
                always_trust=True
            )
            
            if result.ok:
                return DecryptionResult(
                    success=True,
                    decrypted_data=str(result).encode(),
                    fingerprint=result.fingerprint
                )
            else:
                return DecryptionResult(
                    success=False,
                    error=result.status
                )
        
        except Exception as e:
            return DecryptionResult(
                success=False,
                error=str(e)
            )
    
    def encrypt_report(
        self,
        report_file: Path,
        recipients: List[str],
        sign: bool = True,
        remove_original: bool = False,
    ) -> EncryptionResult:
        """
        Encrypt an audit report.
        
        Args:
            report_file: Path to report file
            recipients: List of recipient emails/key IDs
            sign: Sign the report
            remove_original: Remove original file after encryption
            
        Returns:
            EncryptionResult
        """
        result = self.encrypt_file(
            input_file=report_file,
            recipients=recipients,
            sign=sign,
            armor=True
        )
        
        if result.success and remove_original:
            try:
                report_file.unlink()
            except Exception as e:
                result.error = f"Encrypted but failed to remove original: {e}"
        
        return result


class AESEncryption:
    """
    AES encryption for symmetric encryption.
    
    Used for:
    - Temporary data encryption
    - Session encryption
    - Fast bulk encryption
    """
    
    def __init__(self, key: Optional[bytes] = None):
        """
        Initialize AES encryption.
        
        Args:
            key: 32-byte encryption key (generated if not provided)
        """
        from cryptography.fernet import Fernet
        
        if key is None:
            key = Fernet.generate_key()
        
        self.key = key
        self.cipher = Fernet(key)
    
    @staticmethod
    def generate_key() -> bytes:
        """Generate a new AES key."""
        from cryptography.fernet import Fernet
        return Fernet.generate_key()
    
    def encrypt(self, data: bytes) -> bytes:
        """
        Encrypt data with AES.
        
        Args:
            data: Data to encrypt
            
        Returns:
            Encrypted data
        """
        return self.cipher.encrypt(data)
    
    def decrypt(self, encrypted_data: bytes) -> bytes:
        """
        Decrypt AES encrypted data.
        
        Args:
            encrypted_data: Encrypted data
            
        Returns:
            Decrypted data
        """
        return self.cipher.decrypt(encrypted_data)
    
    def encrypt_file(self, input_file: Path, output_file: Path):
        """Encrypt a file with AES."""
        with open(input_file, 'rb') as f:
            data = f.read()
        
        encrypted = self.encrypt(data)
        
        with open(output_file, 'wb') as f:
            f.write(encrypted)
    
    def decrypt_file(self, input_file: Path, output_file: Path):
        """Decrypt an AES encrypted file."""
        with open(input_file, 'rb') as f:
            encrypted = f.read()
        
        decrypted = self.decrypt(encrypted)
        
        with open(output_file, 'wb') as f:
            f.write(decrypted)


# Global encryption instances
_gpg_encryption: Optional[GPGEncryption] = None


def get_gpg_encryption(gnupghome: Optional[Path] = None) -> GPGEncryption:
    """Get global GPG encryption instance."""
    global _gpg_encryption
    if _gpg_encryption is None:
        _gpg_encryption = GPGEncryption(gnupghome=gnupghome)
    return _gpg_encryption
