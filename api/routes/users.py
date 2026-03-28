from fastapi import APIRouter
from models import UserInfo
import database

router = APIRouter()


@router.get("/users", response_model=list[UserInfo])
def list_users():
    """
    Tum kullanicilari ve durumlarini listeler.
    Grup bilgisini PostgreSQL'den, online durumunu Redis'ten alir.
    """
    redis_client = database.get_redis()

    conn = database.db_pool.getconn()
    try:
        cur = conn.cursor()
        cur.execute(
            """SELECT rc.username, COALESCE(rug.groupname, 'unknown')
               FROM radcheck rc
               LEFT JOIN radusergroup rug ON rc.username = rug.username
               GROUP BY rc.username, rug.groupname"""
        )
        rows = cur.fetchall()
        cur.close()
    finally:
        database.db_pool.putconn(conn)

    # Aktif oturumlari Redis'ten al
    active_sessions = redis_client.smembers("active_sessions") if redis_client else set()
    online_users = set()
    for session_id in active_sessions:
        session_data = redis_client.hgetall(f"session:{session_id}")
        if session_data and "username" in session_data:
            online_users.add(session_data["username"])

    users = []
    for username, groupname in rows:
        users.append(UserInfo(
            username=username,
            groupname=groupname,
            is_online=username in online_users
        ))

    return users
