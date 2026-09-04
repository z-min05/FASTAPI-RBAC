"""Fernet 对称加密工具，用于 api_key 等敏感字段的密文存储。"""

from cryptography.fernet import Fernet, InvalidToken

from app.config import settings


def get_fernet() -> Fernet:
    """从 settings.ENCRYPTION_KEY 获取 Fernet 实例。"""
    return Fernet(settings.ENCRYPTION_KEY.encode("utf-8"))


def encrypt(plaintext: str | None) -> str | None:
    """加密明文，返回密文字符串；None 输入返回 None。"""
    if not plaintext:
        return plaintext
    return get_fernet().encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt(ciphertext: str | None) -> str | None:
    """解密密文，返回明文字符串；None 输入返回 None。"""
    if not ciphertext:
        return ciphertext
    try:
        return get_fernet().decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        # 如果解密失败，可能是未加密的旧数据，直接返回原值
        return ciphertext