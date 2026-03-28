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

## 🐍 FastAPI Policy Engine

### 5 Endpoint — Her birinin görevi ne?

| Endpoint | Ne yapıyor? | Kim çağırıyor? |
|----------|-------------|---------------|
| `POST /auth` | Şifre kontrolü + rate-limiting | FreeRADIUS (rlm_rest) |
| `POST /authorize` | Kullanıcının grubunu ve VLAN'ını döner | FreeRADIUS (rlm_rest) |
| `POST /accounting` | Oturum Start/Update/Stop kaydeder | FreeRADIUS (rlm_rest) |
| `GET /users` | Tüm kullanıcıları listeler | Admin (curl/browser) |
| `GET /sessions/active` | Aktif oturumları Redis'ten çeker | Admin (curl/browser) |

### Neden hem SQL hem de REST ile accounting yapıyoruz?
İkisinin rolü farklı:
- **SQL** → Kalıcı kayıt (radacct tablosu) — "3 ay önce kim bağlanmıştı?" sorusuna cevap
- **REST → Redis** → Anlık durum — "Şu an kim bağlı?" sorusuna cevap

PostgreSQL'den "aktif oturumları" sorgulamak mümkün ama yavaş (disk I/O). Redis bellekte çalışıyor — milisaniyede cevap veriyor.

### Rate-limiting nasıl çalışıyor?
Redis'te kullanıcı bazlı sayaç tutuyoruz:
```
failed:testuser → 3  (TTL: 300 saniye)
```
Her yanlış şifrede sayaç 1 artıyor. 5'e ulaşınca "hesap kilitlendi" dönüyoruz. 300 saniye sonra TTL dolunca Redis key'i otomatik siliyor → hesap tekrar açılıyor.

**Neden Redis?** Çünkü bu bilgiyi PostgreSQL'de tutmak gereksiz yavaş olurdu. Her auth isteğinde disk'e yazmak yerine belleğe yazıyoruz. Ayrıca TTL (Time To Live) özelliği Redis'te native — cron job yazmana gerek yok.

---

## 📝 Bu dosya video hazırlığında güncellenir
Her yeni aşamada buraya "ne yaptık, neden yaptık" eklenecek.
