"""网盘账号凭证(cookie/token)的对称加密。区别于 admin token 的 bcrypt 单向哈希——
这里转存时必须能拿回明文喂给 httpx 请求，所以用 Fernet 可逆加密，密钥来自 config。"""

from functools import lru_cache

from cryptography.fernet import Fernet

from config import settings


@lru_cache(maxsize=1)
def _fernet() -> Fernet:
    key = settings.PAN_CREDENTIAL_ENC_KEY
    if not key:
        raise RuntimeError(
            "PAN_CREDENTIAL_ENC_KEY 未配置，无法加解密网盘账号凭证。"
            "生成方式: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )
    return Fernet(key.encode())


def encrypt_credential(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt_credential(ciphertext: str) -> str:
    return _fernet().decrypt(ciphertext.encode()).decode()
