"""Fernet-based encryption for sensitive configuration values (API keys)."""

from __future__ import annotations

import logging
import os

from cryptography.fernet import Fernet, InvalidToken

log = logging.getLogger(__name__)

_fernet: Fernet | None = None


def _get_fernet() -> Fernet:
    """Return a cached Fernet instance, creating one if needed.

    The encryption key is read from the ``ENCRYPTION_KEY`` environment
    variable.  If the variable is not set, a new key is generated
    automatically and a warning is logged so the operator can persist it.
    """
    global _fernet  # noqa: PLW0603
    if _fernet is not None:
        return _fernet

    key = os.getenv("ENCRYPTION_KEY", "")
    if not key:
        key = Fernet.generate_key().decode()
        log.warning(
            "ENCRYPTION_KEY 未配置，已自动生成临时密钥。"
            "请将以下值写入 .env 文件以保证重启后数据可解密：\n"
            "  ENCRYPTION_KEY=%s",
            key,
        )
        os.environ["ENCRYPTION_KEY"] = key

    _fernet = Fernet(key.encode() if isinstance(key, str) else key)
    return _fernet


def encrypt(plain_text: str) -> str:
    """Encrypt *plain_text* and return a URL-safe base64 token string."""
    return _get_fernet().encrypt(plain_text.encode()).decode()


def decrypt(token: str) -> str:
    """Decrypt a Fernet *token* string back to plain text.

    Returns an empty string and logs a warning if decryption fails
    (e.g. key rotation).
    """
    try:
        return _get_fernet().decrypt(token.encode()).decode()
    except (InvalidToken, Exception):
        log.warning("API Key 解密失败，可能 ENCRYPTION_KEY 已变更。")
        return ""


def mask_key(plain_key: str) -> str:
    """Return a masked version of an API key for display purposes.

    Example: ``sk-abc123xyz`` → ``sk-ab****yz``
    """
    if not plain_key:
        return ""
    if len(plain_key) <= 8:
        return plain_key[:2] + "****"
    return plain_key[:4] + "****" + plain_key[-4:]
