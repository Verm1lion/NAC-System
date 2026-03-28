from fastapi import APIRouter
from models import ActiveSession
import database

router = APIRouter()


@router.get("/sessions/active", response_model=list[ActiveSession])
def get_active_sessions():
    """
    Redis'teki aktif oturumlari listeler.

    Neden Redis? Cunku aktif oturumlar surekli degisen, hizli sorgulanmasi
    gereken veriler. PostgreSQL'den her seferinde SELECT yapmak yerine
    Redis'ten aninda okuyoruz.
    """
    redis_client = database.get_redis()

    session_ids = redis_client.smembers("active_sessions")

    sessions = []
    for session_id in session_ids:
        session_data = redis_client.hgetall(f"session:{session_id}")
        if session_data:
            sessions.append(ActiveSession(
                username=session_data.get("username", ""),
                session_id=session_id,
                nas_ip=session_data.get("nas_ip", ""),
                start_time=session_data.get("start_time", ""),
                session_time=int(session_data.get("session_time", 0)),
                input_octets=int(session_data.get("input_octets", 0)),
                output_octets=int(session_data.get("output_octets", 0))
            ))

    return sessions
