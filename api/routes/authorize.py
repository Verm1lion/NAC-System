from fastapi import APIRouter
from models import AuthorizeRequest, AuthorizeResponse
import database

router = APIRouter()


@router.post("/authorize", response_model=AuthorizeResponse)
def authorize_user(request: AuthorizeRequest):
    """
    Yetkilendirme endpoint'i.
    Kullanicinin grubunu bulup, o gruba ait VLAN bilgilerini doner.

    FreeRADIUS bu bilgiyi alip Access-Accept paketine Tunnel attribute'lerini ekler.
    Boylece switch/AP, kullaniciyi dogru VLAN'a atar.
    """
    username = request.username

    conn = database.db_pool.getconn()
    try:
        cur = conn.cursor()

        # Kullanicinin grubunu bul
        cur.execute(
            "SELECT groupname FROM radusergroup WHERE username = %s ORDER BY priority LIMIT 1",
            (username,)
        )
        group_row = cur.fetchone()

        if not group_row:
            cur.close()
            return AuthorizeResponse(
                status="Access-Reject",
                groupname="",
                vlan_id="",
                reply_attributes={}
            )

        groupname = group_row[0]

        # Grubun VLAN attribute'lerini cek
        cur.execute(
            "SELECT attribute, value FROM radgroupreply WHERE groupname = %s",
            (groupname,)
        )
        attrs = cur.fetchall()
        cur.close()

        reply_attrs = {attr: val for attr, val in attrs}
        vlan_id = reply_attrs.get("Tunnel-Private-Group-Id", "")

        return AuthorizeResponse(
            status="Access-Accept",
            groupname=groupname,
            vlan_id=vlan_id,
            reply_attributes=reply_attrs
        )
    finally:
        database.db_pool.putconn(conn)

