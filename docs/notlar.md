# 📓 NAC Projesi — Ne Yaptık, Neden Yaptık?

Bu dosya projeyi yaparken aldığımız her kararı, sade bir dille açıklıyor.
Video çekiminde ve mülakatta "neden böyle yaptın?" sorularına cevap vermek için kullan.

---

## 🏗️ AŞAMA 2-3: Proje İskeleti & Docker Compose

### Ne yaptık?
4 tane servisin tek bir komutla (`docker-compose up -d`) ayağa kalkmasını sağlayan bir altyapı kurduk.

### Servisler neden bu sırayla başlıyor?
```
PostgreSQL → Redis → FastAPI → FreeRADIUS
```
Çünkü **bağımlılık zinciri** var:
- FreeRADIUS'un çalışması için PostgreSQL'de kullanıcılar olmalı
- FreeRADIUS, FastAPI'ye HTTP isteği atacak — API ayakta olmalı
- FastAPI'nin çalışması için PostgreSQL ve Redis'e bağlanması lazım

Docker Compose'daki `depends_on + condition: service_healthy` ayarı bunu garanti ediyor. Yoksa FreeRADIUS daha PostgreSQL hazır olmadan ayağa kalkıp "veritabanına bağlanamıyorum" diye hata verir.

### Neden `healthcheck` ekledik her servise?
`depends_on` tek başına yeterli değil — sadece container'ın "başladığını" kontrol eder, "hazır olduğunu" değil. PostgreSQL container'ı başladı ama veritabanı henüz init.sql'i çalıştırmamış olabilir. `healthcheck` ile "pg_isready" komutunu çalıştırıp gerçekten hazır olduğunu doğruluyoruz.

### Neden dedicated `nac-network` oluşturduk?
Docker varsayılan olarak container'ları birbirine bağlar ama biz kendi network'ümüzü tanımlayarak:
- Servislerin birbirini isimle bulmasını sağladık (örn: `postgres` diye çağırınca PostgreSQL container'ına gidiyor)
- Dışarıdaki container'ların bu sisteme karışmasını engelledik
- Production ortamında da böyle yapılır — izolasyon önemli

### Neden `.env` dosyası kullanıyoruz?
Case'de açıkça söylüyorlar: "secret'lar git'e commit edilmemelidir". `.env` dosyasını `.gitignore`'a ekledik. Yerine `.env.example` dosyası var — bu git'e gider ama şifreler yerine "placeholder" değerler var. Birisi repoyu klonladığında `.env.example`'ı kopyalayıp kendi şifrelerini yazar.

**Alternatif:** Docker Compose'da `environment:` altında direkt yazmak — ama bu güvensiz çünkü `docker-compose.yml` git'e gidiyor.

---

## 🗄️ AŞAMA 4: PostgreSQL Veritabanı

### Neden bu 6 tablo?
Bu tablolar FreeRADIUS'un **standart SQL şeması**. FreeRADIUS yıllardan beri bu tablo yapısıyla çalışıyor:

| Tablo | Ne işe yarıyor? | Örnek |
|-------|-----------------|-------|
| `radcheck` | Kullanıcının şifresi burada | testuser → User123! |
| `radreply` | Kullanıcıya özel dönülecek attribute'lar | (biz grup bazlı yaptık) |
| `radusergroup` | Kullanıcı hangi grupta? | testuser → employee |
| `radgroupreply` | Grubun VLAN ayarları | employee → VLAN 20 |
| `radacct` | Oturum kayıtları | Kim ne zaman bağlandı, kaç MB kullandı |
| `nas` | NAS (switch/AP) tanımları | (opsiyonel) |

### VLAN ataması nasıl çalışıyor?
Üç tane RADIUS attribute'ü birlikte kullanılıyor:
- `Tunnel-Type = VLAN` → "Bu bir VLAN atamasıdır"
- `Tunnel-Medium-Type = IEEE-802` → "Ethernet/Wi-Fi üzerinden"
- `Tunnel-Private-Group-Id = 20` → "VLAN 20'ye at"

Bu üçlüyü birlikte göndermezsek switch anlamaz. Gerçek hayatta switch bu bilgiyi alıp o portu ilgili VLAN'a atar.

### Neden 3 grup (admin, employee, guest)?
Case'de "kullanıcı grupları tanımlanmalıdır" diyor. Gerçek dünyada da böyle çalışır:
- **admin** (VLAN 10): IT ekibi, her yere erişim
- **employee** (VLAN 20): Normal çalışanlar, kısıtlı erişim
- **guest** (VLAN 30): Misafir Wi-Fi, sadece internet

### Neden Cleartext-Password kullanıyoruz?
FreeRADIUS PAP authentication'da bu attribute'ü arar. "Cleartext" adı korkutucu görünebilir ama burada şifre veritabanında tutuluyor ve FreeRADIUS onu PAP modülüyle karşılaştırıyor. Production'da `Crypt-Password` veya `NT-Password` kullanılır — ama case staj ödevi olduğu için Cleartext yeterli ve daha anlaşılır.

**Alternatif:** `SHA-512 Crypt-Password` kullanabilirdik ama FreeRADIUS config'ini karmaşıklaştırırdı. Staj ödevi için overkill.

---

## 🔧 AŞAMA 5: FreeRADIUS Konfigürasyonu

### Neden özel Dockerfile yazdık?
Base image (`freeradius/freeradius-server:latest-3.2`) sadece temel FreeRADIUS'u içerir. Bize ek olarak şunlar lazım:
- `freeradius-postgresql` → SQL modülünün PostgreSQL ile konuşabilmesi
- `freeradius-rest` → REST modülünün FastAPI ile konuşabilmesi

Bu paketler olmadan `rlm_sql_postgresql` ve `rlm_rest` modülleri yüklenmez.

**Alternatif:** `apt-get install` komutlarını `docker-compose.yml`'de `command` olarak yazmak — ama her container restart'ında tekrar yüklenir, verimsiz.

### `clients.conf` ne işe yarıyor?
RADIUS sunucusu rastgele yerlerden gelen istekleri kabul etmez. Hangi cihazlardan (NAS) istek gelebileceğini burada tanımlıyoruz. Docker ortamında tüm servisler aynı network'te olduğu için geniş bir IP aralığı (`172.16.0.0/12`) tanımladık. `shared secret` ise NAS ile RADIUS arasındaki şifre — ikisi de aynı secret'ı bilmeli.

### `rlm_sql` (SQL Modülü) — Neden var?
FreeRADIUS tek başına dosya tabanlı çalışır (`/etc/freeradius/users` dosyası). Ama biz kullanıcıları PostgreSQL'de tutmak istiyoruz çünkü:
- Dinamik kullanıcı ekleme/silme (API üzerinden)
- Accounting kayıtlarını veritabanına yazma
- Binlerce kullanıcıyı yönetebilme

SQL modülü FreeRADIUS'a "kullanıcıları dosyadan değil, veritabanından oku" diyor.

### `rlm_rest` (REST Modülü) — Neden var?
Bu projenin **en güzel parçası**. FreeRADIUS eski bir yazılım (C ile yazılmış), ama `rlm_rest` ile modern bir Python API'ye bağlayabiliyoruz. Bu sayede:
- **Redis rate-limiting**: "5 kere yanlış şifre girdin, 5 dakika bekle" → Bunu FreeRADIUS tek başına yapamaz
- **Dinamik politikalar**: Admin panelinden VLAN değiştirmek → SQL'i direkt değiştirmek yerine API üzerinden
- **Aktif oturum takibi**: Redis'te gerçek zamanlı kim bağlı görme

**Alternatif:** rlm_rest kullanmadan sadece SQL ile yapmak — ama o zaman rate-limiting ve aktif oturum cache'i olmazdı, case'in istediği Redis entegrasyonunu karşılayamazdık.

### `sites-available/default` — Bu dosya ne?
FreeRADIUS'un "ana akış şeması". Bir RADIUS isteği geldiğinde sırayla şu adımlar çalışır:

```
1. AUTHORIZE: "Bu kullanıcı kim?" → SQL'den bilgileri çek
2. AUTHENTICATE: "Şifresi doğru mu?" → PAP modülü kontrol eder
3. POST-AUTH: "Sonucu kaydet" → Başarılı/başarısız log
4. ACCOUNTING: "Oturum verisi" → SQL + REST ile kaydet
```

Her adımda hangi modüllerin çalışacağını biz tanımlıyoruz. Mesela `authorize` bölümünde `sql` ve `rest` yazıyoruz — yani önce SQL'den kullanıcıyı bul, sonra REST API'den ek politika bilgisi al.

---

## 🐛 AŞAMA 7-8: VM'de Deploy ve Debug Süreci

### Karşılaştığımız sorunlar ve nasıl çözdük

Bu bölüm özellikle **video çekimi** ve **mülakat** için çok değerli. Hocalar gerçek dünya deneyimini görmek ister — "her şey ilk seferde çalıştı" demek yerine bu sorunları anlatmak daha etkileyici.

### Sorun 1: FreeRADIUS Access-Reject dönüyordu (doğru şifreye rağmen)

**Belirti:** `radtest testuser User123! localhost 0 testing123` komutu Access-Reject veriyordu, şifre doğru olmasına rağmen.

**Teşhis süreci:**
1. `freeradius -X` ile debug modunda çalıştırdık
2. SQL sorgusunda `WHERE username = ''` gördük — username boş gidiyordu!
3. FreeRADIUS'un SQL modülünde `sql_user_name` değişkeni tanımlı değildi

**Çözüm:** `mods-available/sql` dosyasına eklendi:
```
sql_user_name = "%{%{Stripped-User-Name}:-%{User-Name}}"
```
Bu satır FreeRADIUS'a "RADIUS paketindeki User-Name attribute'ünü al ve SQL sorgusunda `%{SQL-User-Name}` yerine koy" diyor.

**Ders:** Resmi FreeRADIUS SQL konfigürasyonunda bu satır varsayılan olarak var ama biz özel config yazarken atlayınca şema çalışmadı. Config yazarken belgelerin "default" dosyasını referans almak gerekiyor.

---

### Sorun 2: REST modülü TLS hatası veriyordu

**Belirti:** FreeRADIUS başlarken `rlm_rest: ${..tls} is not a valid reference` hatası

**Neden:** REST modülü config'inde TLS ayarları `${..tls}` referansıyla yazılmıştı, ama Docker container içi iletişimde TLS kullanmıyoruz.

**Çözüm:** REST config'inden TLS bloklarını kaldırdık. Container'lar aynı Docker network'te — HTTP yeterli.

**Ders:** Internal servisler arasında TLS genellikle gereksiz karmaşıklık ekler. Zero-trust architecture istiyorsan eklersin ama staj projesinde overhead.

---

### Sorun 3: REST modülü Auth-Type'ı eziyordu

**Belirti:** FreeRADIUS `authorize` bölümünde hem `sql` hem `rest` çalışıyordu. REST modülü `Auth-Type = REST` setliyordu, bu da PAP authentication'ı devre dışı bırakıyordu.

**Çözüm:** `sites-available/default` dosyasının `authorize` bölümünden `rest` modülünü çıkardık. REST'i sadece `accounting` bölümünde bıraktık.

**Mimari karar:** FreeRADIUS `authorize` aşamasında birden fazla modül çalışırsa sonuncu `Auth-Type`'ı kazanır. SQL `Auth-Type = PAP` setliyordu, REST `Auth-Type = REST` setliyordu, REST son çalıştığı için PAP hiç devreye girmiyordu.

---

### Sorun 4: FastAPI `db_pool` NoneType hatası

**Belirti:** `curl http://localhost:8000/users` → 500 Internal Server Error  
Log: `AttributeError: 'NoneType' object has no attribute 'getconn'`

**Neden:** Python import sistemi ile ilgili ince bir bug:
```python
# ❌ YANLIŞ — import zamanında db_pool = None, sonra değişse bile bu referans None kalır
from database import db_pool

# ✅ DOĞRU — her erişimde modülden güncel değeri çeker
import database
conn = database.db_pool.getconn()
```

`database.py`'de `db_pool = None` olarak başlıyor, sonra `init_db()` çağrılınca gerçek pool atanıyor. Ama `from database import db_pool` dediğinde Python o anki değeri (None) alıp route dosyasının scope'una kopyalıyor. Sonradan `database.db_pool` değişse bile route dosyasındaki `db_pool` hâlâ None.

**Çözüm:** Tüm 5 route dosyasında `from database import db_pool` → `import database` olarak değiştirdik.

**Ders:** Python'da mutable module-level değişkenleri `from x import y` ile import etme. Modül referansını import et (`import x`) ve `x.y` ile eriş.

---

### Sorun 5: Accounting 422 Unprocessable Content

**Belirti:** FreeRADIUS accounting paketi gönderiyordu ama FastAPI 422 döndürüyordu.

**Neden:** FreeRADIUS REST modülü boş RADIUS attribute'lerini string olarak gönderiyordu:
```json
{"acct_session_time": "", "acct_input_octets": "", "acct_output_octets": ""}
```
Ama Pydantic modeli bunları `int` olarak bekliyordu. Boş string → int dönüşümü validation hatası veriyordu.

**Çözüm:** `AccountingRequest` modelinde bu alanları `str` yaptık ve `@property` ile güvenli int dönüşümü eklendik:
```python
acct_session_time: str = "0"  # int yerine str

@property
def session_time_int(self) -> int:
    try: return int(self.acct_session_time)
    except: return 0
```

**Ders:** External sistemlerden gelen veriyi asla sıkı tiplemeyle beklememe. FreeRADIUS gibi eski yazılımlar boş string, null, tip uyumsuzluğu gönderebilir. Defensive programming: tip dönüşümlerini explicit yap.

---

## 🎤 Video İçin Anahtar Cümleler

Videoda şu cümleleri kullan (kendi üslubunla):

1. **Mimari açıklarken:**
   - "FreeRADIUS C ile yazılmış 20 yıllık bir yazılım, biz onu modern bir Python API ile genişlettik"
   - "Her servis kendi container'ında çalışıyor — birini değiştirmek diğerlerini etkilemiyor"

2. **VLAN açıklarken:**
   - "Gerçek hayatta switch bu VLAN bilgisini alıp kullanıcının portunu o VLAN'a atar"
   - "Admin yanlış bir Wi-Fi'ye bağlansa bile RADIUS onu VLAN 10'a yönlendirir"

3. **Debug anlatırken:**
   - "İlk denemede authentication çalışmadı — FreeRADIUS debug modunda SQL sorgusunda username'in boş gittiğini gördüm"
   - "Python import sistemiyle ilgili ince bir bug vardı — module-level değişkenler import zamanında kopyalanıyor"

4. **Tasarım kararları:**
   - "Rate-limiting'i neden Redis'te yaptık? PostgreSQL'e her auth isteğinde yazmak gereksiz I/O. Redis in-memory — mikrosaniye"
   - "Accounting'i neden hem SQL hem Redis'e yazıyoruz? SQL kalıcı tarihçe, Redis anlık durum"

---

## 📊 Final Özet

| Bileşen | Durum | Not |
|---------|-------|-----|
| Docker Compose (4 servis) | ✅ Çalışıyor | healthcheck + depends_on |
| PostgreSQL (6 tablo + seed) | ✅ Çalışıyor | FreeRADIUS standart şema |
| FreeRADIUS (SQL + REST) | ✅ Çalışıyor | 3 bug düzeltildi |
| FastAPI (5 endpoint) | ✅ Çalışıyor | db_pool import bug düzeltildi |
| Redis (rate-limit + cache) | ✅ Çalışıyor | TTL ile otomatik kilit açma |
| PAP Authentication | ✅ Test edildi | 3 kullanıcı doğrulandı |
| MAB Authentication | ✅ Test edildi | MAC adresi → guest VLAN |
| VLAN Assignment | ✅ Test edildi | 10/20/30 doğru atanıyor |
| Accounting (Start/Stop) | ✅ Test edildi | PostgreSQL + Redis kaydı |
| Rate-Limiting | ✅ Test edildi | 5 deneme → kilit |

