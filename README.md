# 🔒 NAC System — Network Access Control

RADIUS protokolü tabanlı Network Access Control sistemi.  
**S3M Security** staj değerlendirme projesi.

## Mimari

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

## Teknolojiler

| Servis | Image | Rol |
|--------|-------|-----|
| FreeRADIUS | `freeradius/freeradius-server:latest-3.2` | RADIUS sunucusu — AAA |
| PostgreSQL | `postgres:18-alpine` | Kullanıcı/accounting veritabanı |
| Redis | `redis:8-alpine` | Oturum cache, rate-limiting |
| FastAPI | `python:3.13-slim` | Policy engine API |

## Hızlı Başlangıç

```bash
# 1. Repoyu klonla
git clone <repo-url>
cd nac-system

# 2. Environment dosyasını hazırla
cp .env.example .env
# .env dosyasını düzenle (şifreleri değiştir)

# 3. Tüm sistemi başlat
docker-compose up -d

# 4. Servislerin durumunu kontrol et
docker-compose ps

# 5. Authentication testi
docker-compose exec freeradius radtest testuser User123! localhost 0 testing123
```

## Test Komutları

```bash
# Başarılı authentication
radtest testuser User123! localhost 0 testing123

# Başarısız authentication (yanlış şifre)
radtest testuser wrongpass localhost 0 testing123

# MAB testi (MAC adresi tabanlı)
echo "User-Name=AA:BB:CC:DD:EE:FF,User-Password=AA:BB:CC:DD:EE:FF" | radclient localhost auth testing123

# Accounting Start
echo "Acct-Status-Type=Start,User-Name=testuser,Acct-Session-Id=sess001,NAS-IP-Address=192.168.1.1" | radclient localhost acct testing123

# FastAPI endpoint'leri
curl http://localhost:8000/health
curl http://localhost:8000/users
curl http://localhost:8000/sessions/active
```

## Kullanıcılar (Test)

| Kullanıcı | Şifre | Grup | VLAN |
|-----------|-------|------|------|
| testadmin | Admin123! | admin | 10 |
| testuser | User123! | employee | 20 |
| testguest | Guest123! | guest | 30 |
| AA:BB:CC:DD:EE:FF | AA:BB:CC:DD:EE:FF | guest (MAB) | 30 |

## Proje Yapısı

```
nac-system/
├── docker-compose.yml          # Orkestrasyon
├── .env / .env.example         # Gizli bilgiler
├── freeradius/                 # RADIUS sunucusu config
│   ├── Dockerfile
│   ├── clients.conf            # NAS client tanımları
│   ├── mods-available/sql      # PostgreSQL entegrasyonu
│   ├── mods-available/rest     # FastAPI entegrasyonu
│   └── sites-available/default # İstek işleme pipeline'ı
├── api/                        # FastAPI policy engine
│   ├── main.py                 # App entrypoint
│   ├── config.py               # Environment yönetimi
│   ├── database.py             # DB + Redis bağlantıları
│   ├── models.py               # Pydantic şemaları
│   └── routes/                 # API endpoint'leri
├── postgres/
│   └── init.sql                # Veritabanı şeması + seed data
└── docs/                       # Mimari diyagramlar
```
