from fastapi import APIRouter
import database

router = APIRouter()


@router.get("/stats")
def get_stats():
    """
    Dashboard icin istatistik endpoint'i.
    Redis'ten blocked hesaplari, PostgreSQL'den auth istatistiklerini toplar.
    """
    redis_client = database.get_redis()

    # Redis'teki blocked (rate-limited) hesaplari say
    blocked_count = 0
    try:
        for key in redis_client.scan_iter("failed:*"):
            count = redis_client.get(key)
            if count and int(count) >= 5:
                blocked_count += 1
    except Exception:
        blocked_count = 0

    # Aktif oturum sayisi
    active_sessions = redis_client.scard("active_sessions") if redis_client else 0

    # PostgreSQL'den toplam auth istatistikleri
    total_auths = 0
    successful_auths = 0
    conn = database.db_pool.getconn()
    try:
        cur = conn.cursor()
        # radacct tablosundan toplam oturum sayisi (basarili auth = oturum acilmis)
        cur.execute("SELECT COUNT(*) FROM radacct")
        total_sessions = cur.fetchone()[0]
        successful_auths = total_sessions
        # Basarisiz giris denemelerinin toplam sayisi (Redis'ten)
        failed_total = 0
        for key in redis_client.scan_iter("failed:*"):
            count = redis_client.get(key)
            if count:
                failed_total += int(count)
        total_auths = successful_auths + failed_total
        cur.close()
    except Exception:
        pass
    finally:
        database.db_pool.putconn(conn)

    # Auth success rate hesapla
    auth_success_rate = 0.0
    if total_auths > 0:
        auth_success_rate = round((successful_auths / total_auths) * 100, 1)
    else:
        auth_success_rate = 100.0  # Hic deneme yoksa %100

    return {
        "blocked_accounts": blocked_count,
        "active_sessions": active_sessions,
        "total_auths": total_auths,
        "successful_auths": successful_auths,
        "auth_success_rate": auth_success_rate
    }
