"""
Шифрование сообщений чата — Fernet (symmetric, at-rest encryption).
Ключ выводится из SECRET_KEY через SHA-256, поэтому отдельный секрет не нужен.

Формат хранения в БД:  enc:<base64-fernet-token>
Если строка не начинается с enc: — это старое незашифрованное сообщение,
оно возвращается как есть (обратная совместимость).
"""

import hashlib
import base64

from cryptography.fernet import Fernet, InvalidToken

_fernet: Fernet | None = None

ENC_PREFIX = 'enc:'


def _get_fernet() -> Fernet:
    """Ленивая инициализация — один экземпляр на процесс."""
    global _fernet
    if _fernet is None:
        from django.conf import settings
        raw = settings.SECRET_KEY.encode('utf-8')
        key_bytes = hashlib.sha256(raw).digest()       # 32 bytes
        fernet_key = base64.urlsafe_b64encode(key_bytes)  # Fernet требует urlsafe base64
        _fernet = Fernet(fernet_key)
    return _fernet


def encrypt_text(text: str) -> str:
    """Шифрует строку и возвращает enc:<token>."""
    if not text:
        return text
    token = _get_fernet().encrypt(text.encode('utf-8')).decode('ascii')
    return ENC_PREFIX + token


def decrypt_text(text: str) -> str:
    """
    Расшифровывает строку в формате enc:<token>.
    Если строка не имеет префикса enc: — возвращает как есть (legacy plaintext).
    """
    if not text or not text.startswith(ENC_PREFIX):
        return text
    try:
        token = text[len(ENC_PREFIX):].encode('ascii')
        return _get_fernet().decrypt(token).decode('utf-8')
    except (InvalidToken, Exception):
        # Повреждённые данные — возвращаем raw (видно что что-то не так)
        return text
