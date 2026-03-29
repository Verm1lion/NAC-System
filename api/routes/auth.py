from fastapi import APIRouter
from models import AuthRequest, AuthResponse
import database
from config import MAX_FAILED_ATTEMPTS, LOCKOUT_SECONDS
import hashlib
import base64

router = APIRouter()


def verify_ssha(password: str, stored_hash: str) -> bool:
    """
    SSHA (Salted SHA-1) hash dogrulama.
    stored_hash: base64( SHA1(password + salt) + salt )
    Son 4 byte salt, ilk 20 byte SHA1 digest.
    """
    try:
        decoded = base64.b64decode(stored_hash)
        digest = decoded[:20]  # SHA1 = 20 byte
        salt = decoded[20:]    # kalan = salt (4 byte)
        computed = hashlib.sha1(password.encode('utf-8') + salt).digest()
        return computed == digest
    except Exception:
        return False


@router.post("/auth", response_model=AuthResponse)
def authenticate(request: AuthRequest):
    """
    Kullanici dogrulama endpoint'i.
    FreeRADIUS rlm_rest modulu uzerinden cagirilir.

    Akis:
    1. Redis'ten rate-limit kontrolu yap
    2. PostgreSQL'den kullanici bilgilerini cek
    3. SSHA hash dogrulamasi yap
    4. Basarili/basarisiz sonuca gore islem yap
    """
    redis_client = database.get_redis()
    username = request.username

    # Rate limiting kontrolu
    fail_key = f"failed:{username}"
    fail_count = redis_client.get(fail_key)
    if fail_count and int(fail_count) >= MAX_FAILED_ATTEMPTS:
        return AuthResponse(
            status="Access-Reject",
            message=f"Hesap gecici olarak kilitlendi. {LOCKOUT_SECONDS} saniye bekleyin."
        )

    # Veritabanindan kullanici bilgilerini cek
    # Once SSHA-Password, yoksa Cleartext-Password (MAB icin)
    conn = database.db_pool.getconn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT attribute, value FROM radcheck WHERE username = %s AND attribute IN ('SSHA-Password', 'Cleartext-Password')",
            (username,)
        )
        row = cur.fetchone()
        cur.close()
    finally:
        database.db_pool.putconn(conn)

    if not row:
        _increment_fail_count(redis_client, fail_key)
        return AuthResponse(
            status="Access-Reject",
            message="Kullanici bulunamadi."
        )

    attr_type, stored_value = row

    # Dogrulama: hash tipine gore karsilastir
    if attr_type == 'SSHA-Password':
        password_valid = verify_ssha(request.password, stored_value)
    else:
        # Cleartext-Password (MAB cihazlar icin)
        password_valid = (request.password == stored_value)

    if not password_valid:
        _increment_fail_count(redis_client, fail_key)
        return AuthResponse(
            status="Access-Reject",
            message="Yanlis sifre."
        )

    # Basarili giris — fail sayacini sifirla
    redis_client.delete(fail_key)

    return AuthResponse(
        status="Access-Accept",
        message="Dogrulama basarili."
    )


def _increment_fail_count(redis_client, fail_key: str):
    """Basarisiz giris sayacini arttirir ve TTL ayarlar."""
    redis_client.incr(fail_key)
    redis_client.expire(fail_key, LOCKOUT_SECONDS)
