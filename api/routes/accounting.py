from fastapi import APIRouter
from models import AccountingRequest, AccountingResponse
import database
from datetime import datetime, timezone

router = APIRouter()


@router.post("/accounting", response_model=AccountingResponse)
def handle_accounting(request: AccountingRequest):
    """
    Accounting endpoint'i.
    FreeRADIUS'tan gelen Start/Interim-Update/Stop paketlerini isler.

    - Start: Yeni oturum baslatir, Redis'e ekler, PostgreSQL'e yazar
    - Interim-Update: Oturum verisini gunceller
    - Stop: Oturumu kapatir, Redis'ten siler
    """
    redis_client = database.get_redis()
    status_type = request.acct_status_type.lower()

    if status_type == "start":
        return _handle_start(request, redis_client)
    elif status_type in ("interim-update", "alive"):
        return _handle_interim(request, redis_client)
    elif status_type == "stop":
        return _handle_stop(request, redis_client)
    else:
        return AccountingResponse(
            status="error",
            message=f"Bilinmeyen Acct-Status-Type: {request.acct_status_type}"
        )


def _handle_start(request: AccountingRequest, redis_client):
    """Yeni oturum baslat."""
    now = datetime.now(timezone.utc).isoformat()

    # PostgreSQL'e kaydet
    conn = database.db_pool.getconn()
    try:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO radacct (acctsessionid, username, nasipaddress, acctstarttime, acctuniqueid)
               VALUES (%s, %s, %s, %s, %s)""",
            (request.acct_session_id, request.username, request.nas_ip_address, now, request.acct_session_id)
        )
        conn.commit()
        cur.close()
    finally:
        database.db_pool.putconn(conn)

    # Redis'e aktif oturum olarak ekle
    session_key = f"session:{request.acct_session_id}"
    redis_client.hset(session_key, mapping={
        "username": request.username,
        "nas_ip": request.nas_ip_address,
        "start_time": now,
        "session_time": "0",
        "input_octets": "0",
        "output_octets": "0"
    })
    # Aktif oturumlar set'ine ekle
    redis_client.sadd("active_sessions", request.acct_session_id)

    return AccountingResponse(status="ok", message="Oturum baslatildi.")


def _handle_interim(request: AccountingRequest, redis_client):
    """Oturum verilerini guncelle."""
    # PostgreSQL'i guncelle
    conn = database.db_pool.getconn()
    try:
        cur = conn.cursor()
        cur.execute(
            """UPDATE radacct
               SET acctsessiontime = %s,
                   acctinputoctets = %s,
                   acctoutputoctets = %s,
                   acctupdatetime = %s
               WHERE acctsessionid = %s""",
            (request.session_time_int, request.input_octets_int,
             request.output_octets_int, datetime.now(timezone.utc).isoformat(),
             request.acct_session_id)
        )
        conn.commit()
        cur.close()
    finally:
        database.db_pool.putconn(conn)

    # Redis'teki session verisini guncelle
    session_key = f"session:{request.acct_session_id}"
    redis_client.hset(session_key, mapping={
        "session_time": str(request.session_time_int),
        "input_octets": str(request.input_octets_int),
        "output_octets": str(request.output_octets_int)
    })

    return AccountingResponse(status="ok", message="Oturum guncellendi.")


def _handle_stop(request: AccountingRequest, redis_client):
    """Oturumu kapat."""
    now = datetime.now(timezone.utc).isoformat()

    # PostgreSQL'de oturumu kapat
    conn = database.db_pool.getconn()
    try:
        cur = conn.cursor()
        cur.execute(
            """UPDATE radacct
               SET acctstoptime = %s,
                   acctsessiontime = %s,
                   acctinputoctets = %s,
                   acctoutputoctets = %s,
                   acctterminatecause = 'User-Request'
               WHERE acctsessionid = %s""",
            (now, request.session_time_int, request.input_octets_int,
             request.output_octets_int, request.acct_session_id)
        )
        conn.commit()
        cur.close()
    finally:
        database.db_pool.putconn(conn)

    # Redis'ten sil
    session_key = f"session:{request.acct_session_id}"
    redis_client.delete(session_key)
    redis_client.srem("active_sessions", request.acct_session_id)

    return AccountingResponse(status="ok", message="Oturum kapatildi.")
