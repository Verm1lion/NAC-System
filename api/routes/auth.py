from fastapi import APIRouter
from models import AuthRequest, AuthResponse
import database
from config import MAX_FAILED_ATTEMPTS, LOCKOUT_SECONDS

router = APIRouter()


@router.post("/auth", response_model=AuthResponse)
def authenticate(request: AuthRequest):
    """
    Kullanici dogrulama endpoint'i.
    FreeRADIUS rlm_rest modulu uzerinden cagirilir.

    Akis:
    1. Redis'ten rate-limit kontrolu yap
    2. PostgreSQL'den kullanici bilgilerini cek
    3. Sifre karsilastirmasi yap
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
    conn = database.db_pool.getconn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT value FROM radcheck WHERE username = %s AND attribute = 'Cleartext-Password'",
            (username,)
        )
        row = cur.fetchone()
        cur.close()
    finally:
        database.db_pool.putconn(conn)

    if not row:
        # Kullanici bulunamadi
        _increment_fail_count(redis_client, fail_key)
        return AuthResponse(
            status="Access-Reject",
            message="Kullanici bulunamadi."
        )

    stored_password = row[0]

    if request.password != stored_password:
        # Yanlis sifre
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
