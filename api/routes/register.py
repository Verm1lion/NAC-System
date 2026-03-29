from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import database
import hashlib
import os
import base64
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


class RegisterRequest(BaseModel):
    """Yeni kullanici kaydi icin request modeli."""
    username: str
    password: str
    groupname: str = "guest"  # varsayilan: guest grubu


class RegisterResponse(BaseModel):
    """Kayit sonucu."""
    status: str
    message: str
    username: str
    groupname: str
    vlan_id: str


# Grup -> VLAN eslemesi
GROUP_VLAN_MAP = {
    "admin": "10",
    "employee": "20",
    "guest": "30"
}


def generate_ssha(password: str) -> str:
    """
    SSHA (Salted SHA-1) hash uretir.
    Format: base64( SHA1(password + salt) + salt )
    Salt: 4 byte rastgele deger.
    """
    salt = os.urandom(4)
    sha1_hash = hashlib.sha1(password.encode('utf-8') + salt).digest()
    return base64.b64encode(sha1_hash + salt).decode('ascii')


@router.post("/register", response_model=RegisterResponse)
def register_user(request: RegisterRequest):
    """
    Yeni kullanici kayit endpoint'i.

    Akis:
    1. Kullanici adi bosluk/gecersizlik kontrolu
    2. Ayni kullanici var mi kontrol et
    3. Sifreyi SSHA ile hashle
    4. radcheck tablosuna hash'li sifre kaydet
    5. radusergroup tablosuna grup atamasini yap
    """
    username = request.username.strip()
    password = request.password.strip()
    groupname = request.groupname.strip().lower()

    # Validasyon
    if not username or not password:
        raise HTTPException(status_code=400, detail="Username ve password bos olamaz.")

    if len(password) < 6:
        raise HTTPException(status_code=400, detail="Sifre en az 6 karakter olmalidir.")

    if groupname not in GROUP_VLAN_MAP:
        raise HTTPException(
            status_code=400,
            detail=f"Gecersiz grup. Gecerli gruplar: {', '.join(GROUP_VLAN_MAP.keys())}"
        )

    conn = database.db_pool.getconn()
    try:
        cur = conn.cursor()

        # Kullanici zaten var mi?
        cur.execute("SELECT id FROM radcheck WHERE username = %s", (username,))
        if cur.fetchone():
            raise HTTPException(status_code=409, detail=f"'{username}' kullanicisi zaten kayitli.")

        # SSHA hash uret
        ssha_hash = generate_ssha(password)

        # radcheck'e kaydet
        cur.execute(
            "INSERT INTO radcheck (username, attribute, op, value) VALUES (%s, 'SSHA-Password', ':=', %s)",
            (username, ssha_hash)
        )

        # radusergroup'a grup atamasini yap
        cur.execute(
            "INSERT INTO radusergroup (username, groupname, priority) VALUES (%s, %s, 1)",
            (username, groupname)
        )

        conn.commit()
        cur.close()

        logger.info(f"Yeni kullanici kaydi: {username} -> {groupname} (VLAN {GROUP_VLAN_MAP[groupname]})")

        return RegisterResponse(
            status="ok",
            message=f"Kullanici '{username}' basariyla kaydedildi.",
            username=username,
            groupname=groupname,
            vlan_id=GROUP_VLAN_MAP[groupname]
        )

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Register hatasi: {e}")
        raise HTTPException(status_code=500, detail="Kayit sirasinda hata olustu.")
    finally:
        database.db_pool.putconn(conn)
