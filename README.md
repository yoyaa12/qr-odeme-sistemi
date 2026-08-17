# Restoran QR Kodlu Sipariş ve Operasyon Sistemi

FastAPI, WebSockets (Socket.IO) ve MS SQL Server kullanılarak geliştirilmiş gerçek zamanlı Restoran QR Sipariş, Mutfak ve Garson Takip Otomasyonu.

## Mimari Yapı

Sistem 3 temel katman üzerine inşa edilmiştir:

1. **Sunum Katmanı:**
   - Müşteri QR Menü Arayüzü (`/menu?masa=1`)
   - Mutfak Operasyon Paneli (`/mutfak`)
   - Garson Operasyon Paneli (`/garson`)
   - Kasa Paneli (`/kasa`)
   - Yönetici Paneli (`/admin`)

2. **İş Mantığı Katmanı:**
   - Sipariş ve sepet yönetimi
   - Ödeme akışı yönetimi (Nakit / POS)
   - Gerçek zamanlı bildirim ve durum takibi (WebSockets)
   - Stok güncelleme ve kontrol işlemleri

3. **Veri Katmanı:**
   - MS SQL Server üzerinde Masalar, Ürünler, Kategoriler, Siparişler, SiparişDetayları ve Kullanıcılar tabloları ile ilişkisel veri yönetimi.

## Sipariş Akışı

```
QR Menü -> Sepet -> Sipariş Oluşturma -> Ödeme (Nakit/POS) -> Mutfak -> Garson -> Masaya Teslim
```

- **POS (Dijital Ödeme):** Ödeme anında onaylanır ve sipariş direkt mutfak paneline aktarılır.
- **Nakit Ödeme:** Sipariş "Nakit Bekliyor" durumunda oluşturulur, garson masadan ödemeyi tahsil edip onayladıktan sonra mutfağa düşer. Ödeme tamamlanmadan sipariş mutfağa aktarılmaz.

## Proje Yol Haritası ve Tamamlanan Modüller

- **P0 - Temel Altyapı ve Veritabanı:** İlişkisel veritabanı tasarımı, CRUD modelleri, yönetici paneli ve temel veritabanı yapılandırması.
- **P1 - Müşteri Arayüzü ve Sipariş Akışı:** QR menü, kategorili ürün listeleme, sepet işlemleri, ürün notu / detay seçimi ve sipariş tamamlama.
- **P2 - Operasyon Panelleri (Mutfak & Garson):** Masaların kart görünümü, sipariş detayları, "Hazırlanıyor", "Hazır" ve "Teslim Edildi" durum güncellemeleri.
- **P3 - Gerçek Zamanlı Takip (WebSockets):** Socket.IO ile canlı sipariş düşmesi, anlık durum değişiklikleri ve sesli/görsel uyarılar.
- **P4 - Kullanıcı ve Rol Yönetimi:** Mutfak, garson ve admin panellerinin ayrılması, rol bazlı sipariş durum güncellemeleri.
- **P5 - Stok ve Operasyon Yönetimi:** Sipariş sonrası otomatik stok düşümü ve menü güncelleme kontrolleri.

---

## Kurulum ve Çalıştırma

### 1. Bağımlılıkların Yüklenmesi

Sanal ortam oluşturup gerekli paketleri yükleyin:

```bash
python -m venv .venv
```

Sanal ortamı aktif edin:
- Windows (PowerShell): `.\.venv\Scripts\Activate`
- Linux / macOS: `source .venv/bin/activate`

Paketleri yükleyin:
```bash
pip install -r requirements.txt
```

### 2. Ortam Değişkenleri (.env)

`.env.example` dosyasını `.env` olarak kopyalayıp değerleri doldurun:

```bash
cp .env.example .env
```

Windows (PowerShell) için:

```bash
Copy-Item .env.example .env
```

Doldurulması gereken değişkenler:

| Değişken | Zorunlu | Açıklama |
| --- | --- | --- |
| `DB_SERVER` | evet | SQL Server örneği (ör. `.\SQLEXPRESS`) |
| `DB_NAME` | evet | Veritabanı adı |
| `DB_USER` / `DB_PASSWORD` | hayır | SQL kimlik doğrulaması kullanılıyorsa doldurulur |
| `DB_TRUSTED_CONNECTION` | hayır | Windows kimlik doğrulaması için `yes` (varsayılan) |
| `PORT` | hayır | Varsayılan `8000` |
| `AUTH_SECRET_KEY` | **evet** | Personel JWT imzalama anahtarı, **en az 32 bayt** |
| `AUTH_STAFF_TOKEN_TTL_SECONDS` | hayır | Token ömrü, varsayılan `2592000` (30 gün) |

`AUTH_SECRET_KEY` tanımlı değilse veya 32 bayttan kısaysa uygulama açılışta
`AuthConfigurationError` fırlatır. Rastgele bir anahtar üretmek için:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

### 3. Veritabanı Bağlantısı

Uygulama önce `pyodbc` ile bağlanmayı dener; bunun için
[Microsoft ODBC Driver 17 veya 18 for SQL Server](https://learn.microsoft.com/sql/connect/odbc/download-odbc-driver-for-sql-server)
kurulu olmalıdır. Uygun bir ODBC sürücüsü bulunamazsa `pymssql`'e düşülür.

### 4. Uygulamanın Başlatılması

```bash
python run.py
```

Uygulama çalıştıktan sonra aşağıdaki adreslerden erişilebilir:
- **Ana Ekran:** http://localhost:8000/
- **Müşteri Menüsü:** http://localhost:8000/menu?masa=1
- **Mutfak Paneli:** http://localhost:8000/mutfak
- **Garson Paneli:** http://localhost:8000/garson
- **Kasa Paneli:** http://localhost:8000/kasa
- **Yönetici Paneli:** http://localhost:8000/admin

## Testler

Testler yalnızca standart kütüphaneleri kullanır, ek bağımlılık gerektirmez.

Python tarafı (`unittest`):

```bash
python -m unittest discover -s tests -v
```

Frontend sözleşme testleri (Node.js 18+ yerleşik test koşucusu):

```bash
node --test "tests/frontend/**/*.test.cjs"
```

## Lisans

MIT — ayrıntılar için [LICENSE](LICENSE) dosyasına bakınız.
