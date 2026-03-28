# 🔒 NAC System — Network Access Control

RADIUS protokolü tabanlı, konteynerize edilmiş Network Access Control sistemi.  
**S3M Security** staj değerlendirme projesi.

## 📐 Mimari

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────┐
│  radtest /  │────▶│   FreeRADIUS     │────▶│ PostgreSQL  │
│  radclient  │     │  (Auth/Authz/    │     │ (radcheck,  │
│  (Test)     │◀────│   Accounting)    │◀────│  radacct..) │
└─────────────┘     └────────┬─────────┘     └─────────────┘
                             │ rlm_rest
                             ▼
                    ┌──────────────────┐     ┌─────────────┐
                    │  FastAPI Policy  │────▶│   Redis     │
                    │  Engine (:8000)  │◀────│ (Sessions,  │
                    │  /auth /authorize│     │  Rate-limit)│
                    │  /accounting     │     └─────────────┘
                    └──────────────────┘
```

### Veri Akışı

1. **Authentication** — Kullanıcı/cihaz bağlantı isteği gönderir → FreeRADIUS `rlm_sql` ile PostgreSQL'den şifre doğrular → PAP modülü karşılaştırır → Access-Accept/Reject
2. **Authorization** — Kullanıcının grubu belirlenir → Gruba ait VLAN ID (`radgroupreply`) çekilir → Tunnel attribute'leri Access-Accept'e eklenir
3. **Accounting** — Start/Stop/Interim paketleri → FreeRADIUS `rlm_rest` ile FastAPI'ye gönderir → API hem PostgreSQL'e kaydeder hem Redis'e cache'ler

## 🛠️ Teknolojiler

| Servis | Image | Port | Rol |
|--------|-------|------|-----|
| FreeRADIUS 3.2 | `freeradius/freeradius-server:latest-3.2` | 1812/udp, 1813/udp | RADIUS sunucusu — AAA |
| PostgreSQL 18 | `postgres:18-alpine` | 5432 | Kullanıcı/grup/accounting veritabanı |
| Redis 8 | `redis:8-alpine` | 6379 | Aktif oturum cache, rate-limiting |
| FastAPI | `python:3.13-slim` | 8000 | Policy engine API |

## 🚀 Hızlı Başlangıç

```bash
# 1. Repoyu klonla
git clone https://github.com/Verm1lion/NAC-System.git
cd NAC-System

# 2. Environment dosyasını hazırla
cp .env.example .env
# İsterseniz .env dosyasındaki şifreleri değiştirin

# 3. Tüm sistemi başlat
docker compose up -d

# 4. Servislerin durumunu kontrol et (4/4 healthy olmalı)
docker compose ps

# 5. İlk test — employee kullanıcı
docker compose exec freeradius radtest testuser User123! localhost 0 testing123
# Beklenen: Access-Accept + VLAN 20
```

## ✅ Test Sonuçları (Doğrulanmış)

### Authentication (PAP)

| Test | Komut | Sonuç |
|------|-------|-------|
| Admin girişi | `radtest testadmin Admin123! localhost 0 testing123` | ✅ Access-Accept, VLAN 10 |
| Employee girişi | `radtest testuser User123! localhost 0 testing123` | ✅ Access-Accept, VLAN 20 |
| Guest girişi | `radtest testguest Guest123! localhost 0 testing123` | ✅ Access-Accept, VLAN 30 |
| Yanlış şifre | `radtest testuser wrongpass localhost 0 testing123` | ✅ Access-Reject |

### MAC Authentication Bypass (MAB)

```bash
docker compose exec freeradius radtest AA:BB:CC:DD:EE:FF AA:BB:CC:DD:EE:FF localhost 0 testing123
# ✅ Access-Accept, VLAN 30 (guest grubuna atandı)
```

### Accounting (Start/Stop)

```bash
# Oturum başlat
docker compose exec freeradius bash -c 'echo "Acct-Status-Type=Start,User-Name=testuser,Acct-Session-Id=sess001,NAS-IP-Address=192.168.1.1" | radclient localhost acct testing123'
# ✅ Accounting-Response alındı

# Aktif oturumu doğrula
curl http://localhost:8000/sessions/active
# ✅ [{"username":"testuser","session_id":"sess001",...}]

# Oturumu kapat
docker compose exec freeradius bash -c 'echo "Acct-Status-Type=Stop,User-Name=testuser,Acct-Session-Id=sess001,NAS-IP-Address=192.168.1.1,Acct-Session-Time=300" | radclient localhost acct testing123'
# ✅ Oturum Redis'ten silindi, PostgreSQL'de acctstoptime dolu
```

### Rate-Limiting

```bash
# 6 kez yanlış şifre dene (API üzerinden)
for i in {1..6}; do
  curl -s -X POST http://localhost:8000/auth \
    -H "Content-Type: application/json" \
    -d '{"username":"testuser","password":"yanlis"}'
done
# İlk 5: {"status":"Access-Reject","message":"Yanlis sifre."}
# 6. deneme: {"status":"Access-Reject","message":"Hesap gecici olarak kilitlendi. 300 saniye bekleyin."}
# ✅ Redis sayacı: failed:testuser = 5
```

### FastAPI Endpoint'leri

```bash
curl http://localhost:8000/health          # ✅ {"status":"ok"}
curl http://localhost:8000/users           # ✅ 4 kullanıcı listesi
curl http://localhost:8000/sessions/active # ✅ Aktif oturum listesi
```

## 👥 Test Kullanıcıları

| Kullanıcı | Şifre | Grup | VLAN | Açıklama |
|-----------|-------|------|------|----------|
| testadmin | Admin123! | admin | 10 | IT yönetici — tam erişim |
| testuser | User123! | employee | 20 | Normal çalışan — kısıtlı erişim |
| testguest | Guest123! | guest | 30 | Misafir — sadece internet |
| AA:BB:CC:DD:EE:FF | AA:BB:CC:DD:EE:FF | guest (MAB) | 30 | Cihaz bazlı doğrulama |

## 🔌 API Reference

### `POST /auth` — Kullanıcı Doğrulama
```json
// Request
{"username": "testuser", "password": "User123!"}

// Response (başarılı)
{"status": "Access-Accept", "message": "Dogrulama basarili."}

// Response (kilitli hesap)
{"status": "Access-Reject", "message": "Hesap gecici olarak kilitlendi. 300 saniye bekleyin."}
```

### `POST /authorize` — Yetkilendirme
```json
// Request
{"username": "testuser"}

// Response
{"status": "Access-Accept", "groupname": "employee", "vlan_id": "20", "reply_attributes": {"Tunnel-Type": "VLAN", "Tunnel-Medium-Type": "IEEE-802", "Tunnel-Private-Group-Id": "20"}}
```

### `POST /accounting` — Oturum Kaydı
```json
// Request
{"username": "testuser", "acct_status_type": "Start", "acct_session_id": "sess001", "nas_ip_address": "192.168.1.1"}

// Response
{"status": "ok", "message": "Oturum baslatildi."}
```

### `GET /users` — Kullanıcı Listesi
### `GET /sessions/active` — Aktif Oturumlar
### `GET /health` — Sistem Durumu

## 📁 Proje Yapısı

```
nac-system/
├── docker-compose.yml            # 4 servis orkestrasyonu
├── .env / .env.example           # Environment değişkenleri
├── freeradius/                   # RADIUS sunucusu
│   ├── Dockerfile                # freeradius-postgresql + rest eklentileri
│   ├── clients.conf              # NAS client tanımları (Docker network)
│   ├── mods-available/sql        # PostgreSQL sorgu konfigürasyonu
│   ├── mods-available/rest       # FastAPI REST entegrasyonu
│   └── sites-available/default   # RADIUS istek işleme pipeline'ı
├── api/                          # FastAPI policy engine
│   ├── Dockerfile                # Python 3.13-slim + uvicorn
│   ├── main.py                   # Uygulama giriş noktası + lifespan
│   ├── config.py                 # Environment yönetimi
│   ├── database.py               # PostgreSQL pool + Redis bağlantıları
│   ├── models.py                 # Pydantic request/response şemaları
│   └── routes/
│       ├── auth.py               # POST /auth — rate-limited authentication
│       ├── authorize.py          # POST /authorize — grup + VLAN lookup
│       ├── accounting.py         # POST /accounting — Start/Stop/Interim
│       ├── users.py              # GET /users — kullanıcı listesi
│       └── sessions.py           # GET /sessions/active — Redis'ten okuma
├── postgres/
│   └── init.sql                  # FreeRADIUS standart şeması + seed data
└── docs/
    └── notlar.md                 # Teknik kararlar ve debug notları
```

## 🔒 Güvenlik Önlemleri

- **Secret yönetimi:** Tüm hassas bilgiler `.env` dosyasında, `.gitignore` ile korunuyor
- **SQL Injection koruması:** Tüm sorgularda parameterized queries (`%s` placeholder)
- **Rate-limiting:** Redis tabanlı — 5 başarısız giriş sonrası 300 saniye kilit
- **RADIUS shared secret:** NAS-RADIUS iletişimi `testing123` ile şifreli
- **Ağ izolasyonu:** Docker bridge network ile servisler izole

## 📜 Lisans

S3M Security staj değerlendirme projesidir.
