from pydantic import BaseModel
from typing import Optional
from datetime import datetime


# ---- FreeRADIUS'tan gelen request modelleri ----

class AuthRequest(BaseModel):
    """FreeRADIUS'un /auth endpoint'ine gonderecegi veri."""
    username: str
    password: str


class AuthorizeRequest(BaseModel):
    """FreeRADIUS'un /authorize endpoint'ine gonderecegi veri."""
    username: str


class AccountingRequest(BaseModel):
    """FreeRADIUS'un /accounting endpoint'ine gonderecegi veri."""
    username: str
    acct_status_type: str  # Start, Interim-Update, Stop
    acct_session_id: str
    nas_ip_address: str = ""
    acct_session_time: str = "0"
    acct_input_octets: str = "0"
    acct_output_octets: str = "0"

    @property
    def session_time_int(self) -> int:
        try:
            return int(self.acct_session_time)
        except (ValueError, TypeError):
            return 0

    @property
    def input_octets_int(self) -> int:
        try:
            return int(self.acct_input_octets)
        except (ValueError, TypeError):
            return 0

    @property
    def output_octets_int(self) -> int:
        try:
            return int(self.acct_output_octets)
        except (ValueError, TypeError):
            return 0


# ---- Response modelleri ----

class AuthResponse(BaseModel):
    """Authentication sonucu."""
    status: str  # "Access-Accept" veya "Access-Reject"
    message: str
    reply_attributes: dict = {}


class AuthorizeResponse(BaseModel):
    """Authorization sonucu — VLAN ve policy bilgileri."""
    status: str
    groupname: str = ""
    vlan_id: str = ""
    reply_attributes: dict = {}


class AccountingResponse(BaseModel):
    """Accounting islem sonucu."""
    status: str
    message: str


class UserInfo(BaseModel):
    """Kullanici bilgisi."""
    username: str
    groupname: str
    is_online: bool = False
    last_seen: Optional[datetime] = None


class ActiveSession(BaseModel):
    """Aktif oturum bilgisi."""
    username: str
    session_id: str
    nas_ip: str
    start_time: str
    session_time: int = 0
    input_octets: int = 0
    output_octets: int = 0
