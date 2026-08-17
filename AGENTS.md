# AGENTS.md

## Proje ve Yapay Zeka Çalışma Kuralları

Bu repository; QR tabanlı restoran menü, sipariş, ödeme, mutfak, garson,
kasa ve admin sistemini içeren bir staj projesidir.

Bu dosyadaki kurallar projede çalışan TÜM AI agentları için zorunludur.

Bu kurallar yalnızca mevcut sohbet için değil, repository üzerinde yapılacak
gelecekteki geliştirmeler için de geçerlidir.

---

# 1. Temel Çalışma Prensibi

AI agent yalnızca mevcut chat/context hafızasına güvenmeyecektir.

Repository içindeki dosyalar kalıcı proje hafızası olarak kullanılacaktır.

Her implementation çalışmasından önce aşağıdaki dosyalar okunmalıdır:

1. `AGENTS.md`
2. `docs/SECURITY_AUTH_REFACTOR.md`
3. `docs/IMPLEMENTATION_STATUS.md`
4. `docs/CODEX_CHANGELOG.md`

Bu dosyaların görevleri:

- `AGENTS.md`
  - Agent'ın NASIL çalışacağını belirler.
  - Projenin varsayılan ve zorunlu çalışma kurallarını içerir.

- `docs/SECURITY_AUTH_REFACTOR.md`
  - Security/authentication/refactor kapsamında NE yapılacağını tanımlar.

- `docs/IMPLEMENTATION_STATUS.md`
  - Projenin ŞU ANDA hangi aşamada olduğunu gösterir.

- `docs/CODEX_CHANGELOG.md`
  - Gerçekte hangi dosyaların, neden ve nasıl değiştirildiğinin geçmişini tutar.

Mevcut kullanıcı talebi bu dokümanlardan biriyle çelişirse:

- En son açık ve spesifik kullanıcı talimatı önceliklidir.
- Değişen karar ilgili dokümana kaydedilmelidir.
- Eski karar sessizce değiştirilmemelidir.
- Önemli business/security davranışları kullanıcı talimatı olmadan keyfi olarak değiştirilmemelidir.

---

# 2. Resume / Yeni Session Protokolü

Her yeni Codex / AI çalışma oturumunun başında:

1. `AGENTS.md` dosyasını tamamen oku.
2. `docs/SECURITY_AUTH_REFACTOR.md` dosyasını oku.
3. `docs/IMPLEMENTATION_STATUS.md` dosyasını tamamen oku.
4. `docs/CODEX_CHANGELOG.md` içindeki en son ilgili kayıtları oku.
5. Mevcut Git status / Git diff durumunu incele.
6. Dokümantasyonda tamamlandı yazan önemli değişiklikleri gerçek kod üzerinden doğrula.
7. İlk tamamlanmamış milestone veya task'tan devam et.

Önceki agent'ın:

> Completed

yazmış olması tek başına yeterli değildir.

Özellikle security-sensitive değişikliklerin gerçekten kodda uygulanmış ve
test edilmiş olduğunu doğrula.

Tamamlanmış işi gereksiz yere yeniden yapma.

Ancak verification sonucunda eksik veya hatalı olduğu görülürse düzelt.

---

# 3. Source of Truth Kuralları

`docs/SECURITY_AUTH_REFACTOR.md` mevcut security/authentication/refactor
çalışmasının gereksinim kaynağıdır.

Bu dokümandaki gereksinimler:

- sessizce silinmeyecek,
- zayıflatılmayacak,
- uygulanmadığı halde completed olarak işaretlenmeyecek,
- mevcut eksik implementasyona uydurulmak için yeniden yorumlanmayacaktır.

Implementation sırasında bir gereksinimin teknik açıdan yanlış,
gereksiz veya mevcut mimari için uygun olmadığı ortaya çıkarsa:

1. Problemi gerçek kod üzerinden doğrula.
2. `docs/IMPLEMENTATION_STATUS.md` içine discovery olarak kaydet.
3. Alternatif çözümü açıkla.
4. Değişiklik önemli business/security davranışını etkiliyorsa kullanıcıya bildir.
5. Kullanıcı onayı gerekiyorsa implementation'ı blocker olarak durdur.
6. Gereksinimi sessizce değiştirme.

Özellikle aşağıdaki konular kullanıcı onayı olmadan temel şekilde
değiştirilmemelidir:

- database schema / migration,
- TOTP / QR fiziksel doğrulama davranışı,
- mevcut authentication modelinin temel çalışma mantığı,
- önemli API contract değişiklikleri,
- önemli business-rule değişiklikleri,
- Redis / RabbitMQ / Kafka gibi yeni büyük infrastructure dependency eklenmesi.

---

# 4. Mandatory Progress Tracking

`docs/IMPLEMENTATION_STATUS.md` bir living document'tır.

Sadece başlangıç planı değildir.

Çalışma ilerledikçe sürekli güncel tutulmalıdır.

Her anlamlı milestone sonrasında:

- tamamlanan işleri `[x]` olarak işaretle,
- devam eden işleri belirt,
- yeni discovery'leri kaydet,
- security finding'leri kaydet,
- blocker'ları kaydet,
- test durumunu kaydet,
- verilen önemli mimari kararları kaydet,
- exact next action bölümünü güncelle.

Bir milestone:

- implement edilmediyse,
- gerekli testler çalıştırılmadıysa,
- test sonucu doğrulanmadıysa

`COMPLETED` olarak işaretlenemez.

Yeni bir Codex session'ı hiçbir eski chat mesajını görmeden yalnızca
`docs/IMPLEMENTATION_STATUS.md` okuyarak:

- nerede kalındığını,
- neyin tamamlandığını,
- neyin eksik olduğunu,
- sırada ne olduğunu

anlayabilmelidir.

---

# 5. Mandatory Codex Changelog

`docs/CODEX_CHANGELOG.md` sürekli korunacaktır.

Her anlamlı implementation batch sonrasında yeni bir entry eklenmelidir.

Önceki kayıtlar silinmemeli veya yeniden yazılmamalıdır.

Yalnızca açık bir factual error varsa düzeltilebilir.

Her entry mümkün olduğunca şu bilgileri içermelidir:

- tarih / saat,
- milestone / task,
- kısa summary,
- oluşturulan dosyalar,
- değiştirilen dosyalar,
- silinen dosyalar,
- database değişiklikleri,
- migration gereksinimleri,
- API değişiklikleri,
- authentication değişiklikleri,
- authorization değişiklikleri,
- test değişiklikleri,
- çalıştırılan testler,
- test sonuçları,
- verification,
- mimari kararlar,
- security impact,
- unresolved issues,
- exact next action.

Vague changelog yazma.

Kötü örnek:

> Updated authentication.

İyi örnek:

> Modified `app/auth/dependencies.py` to validate STAFF JWT access tokens before
> protected controllers execute. Added expiration and token-type validation so
> `CUSTOMER_SESSION` tokens cannot access staff routes.

Her önemli dosya için:

- NE değişti?
- NEDEN değişti?

kısaca belirtilmelidir.

---

# 6. Context Kaybına Karşı Koruma

Repository dokümantasyonu chat/context hafızasından daha kalıcı kabul edilmelidir.

Bitmemiş işler yalnızca conversation context içerisinde tutulmamalıdır.

Context azalıyor, session kapanmak üzere veya çalışma yarıda kalacaksa:

1. Yeni büyük bir implementasyona başlama.
2. Mevcut küçük ve güvenli çalışma birimini tamamla.
3. Mümkün olan testleri çalıştır.
4. `docs/IMPLEMENTATION_STATUS.md` güncelle.
5. `docs/CODEX_CHANGELOG.md` güncelle.
6. Unresolved problem'leri yaz.
7. Exact next action'ı yaz.

Amaç:

Yeni bir agent eski conversation geçmişine erişmeden güvenli şekilde devam
edebilmelidir.

---

# 7. Planning ve Implementation Protokolü

Security/authentication/refactor çalışması büyük ve çok aşamalıdır.

Kontrolsüz repository-wide rewrite yapılmayacaktır.

Her major milestone için:

1. Mevcut implementasyonu incele.
2. Etkilenecek dosyaları belirle.
3. Mevcut davranışı anla.
4. Planlanan değişikliği belirle.
5. Küçük ve kontrollü şekilde implement et.
6. Gerekli testleri ekle/güncelle.
7. Testleri çalıştır.
8. Git diff'i incele.
9. `docs/IMPLEMENTATION_STATUS.md` güncelle.
10. `docs/CODEX_CHANGELOG.md` dosyasına entry ekle.
11. Sonraki adıma geç.

Mevcut çalışan davranış, requirement tarafından özellikle değiştirilmediği
sürece korunmalıdır.

---

# 8. Dürüstlük ve Doğrulama Zorunluluğu

## Test Edilmemiş Özellik Eklenmemiş Özelliktir

Yapılan her anlamlı:

- fix,
- refactor,
- feature,
- authentication değişikliği,
- authorization değişikliği,
- business-rule değişikliği

sonrasında ilgili testler çalıştırılmalıdır.

Test sonucu uydurulmayacaktır.

Şunlar yapılmayacaktır:

- çalıştırılmamış teste "passed" demek,
- tahmin edilen sonucu gerçek sonuç gibi yazmak,
- okunmamış kod hakkında varsayım yapmak,
- log görülmeden davranış hakkında kesin hüküm vermek.

Emin olunmayan durumda:

1. Kaynak kodu incele.
2. Testi çalıştır.
3. Log / response / actual runtime behavior üzerinden doğrula.
4. Sonra raporla.

---

# 9. Security Temel Paradigması

Frontend bir güvenlik sınırı DEĞİLDİR.

Bir client'ın frontend'i tamamen bypass edebileceği varsayılacaktır.

Örneğin:

- Browser DevTools,
- F12 Network / Console,
- doğrudan HTTP request,
- curl,
- Postman,
- Python script,
- custom HTTP client

kullanılabilir.

Bu nedenle security-sensitive kurallar backend tarafından enforce edilmelidir.

Özellikle:

- Authentication
- Authorization
- Role checks
- Object ownership
- Table/session ownership
- Order ownership
- Order state transitions
- Payment status
- Price calculation
- Order total
- Product availability
- Quantity validation

frontend kontrolüne bırakılamaz.

---

# 10. Client Tarafından Gönderilen Verilere Güvenmeme

Aşağıdaki client-supplied alanlar hiçbir zaman otomatik olarak trusted kabul
edilmemelidir:

- table ID
- user ID
- role
- order ID ownership
- order status
- payment status
- product price
- order total
- resource ownership
- session ownership
- authentication type

Örneğin client:

```json
{
  "product_id": 10,
  "quantity": 2,
  "price": 1
}
```

gönderebilir.

Backend:

- `product_id` değerini doğrulamalı,
- `quantity` değerini doğrulamalı,
- ürünün gerçek fiyatını database üzerinden almalı,
- request içindeki `price` değerini authoritative kabul etmemeli,
- toplam tutarı backend tarafında hesaplamalıdır.

Aynı şekilde `table_id` mümkün olduğunca authenticated customer session
üzerinden belirlenmelidir.

Client'ın gönderdiği:

- `role`,
- `payment_status`,
- `order_status`,
- `user_id`

gibi kritik alanlara doğrudan güvenilmemelidir.

---

# 11. Authentication ve Authorization Ayrımı

Authentication:

> Bu request'i atan kişi / session kim?

Authorization:

> Bu kişi veya session bu işlemi yapmaya yetkili mi?

Bu iki kavram ayrı uygulanmalıdır.

Örneğin geçerli bir `WAITER` tokenı:

`/api/admin/...`

endpointine gönderildiğinde authentication başarılı olabilir fakat authorization
başarısız olmalıdır.

Uygun response:

`403 Forbidden`

Token:

- yoksa,
- bozuksa,
- geçersizse,
- süresi geçmişse

uygun durumda:

`401 Unauthorized`

kullanılmalıdır.

---

# 12. Controller / Service / Repository Güvenlik Sınırları

Tercih edilen request akışı:

```text
HTTP Request
→ Authentication Filter / Middleware / Dependency
→ Authorization
→ Controller / Router
→ Service
→ Repository
→ Database
```

Authentication ve temel route authorization mümkün olduğunca reusable
dependency/filter/middleware üzerinden uygulanmalıdır.

Her controller içinde aynı token validation kodunu kopyalayıp yapıştırma.

Ancak authorization sadece controller seviyesinde kalmamalıdır.

Service katmanı ayrıca:

- bu spesifik resource'a erişilebilir mi,
- bu role bu business operation izinli mi,
- requested state transition geçerli mi,
- resource mevcut actor/session ile ilişkili mi

gibi business authorization kontrollerini yapmalıdır.

---

# 13. Role-Based Access Control

Staff kullanıcıları için role-based authorization uygulanacaktır.

Mevcut proje ihtiyacına göre roller örneğin:

- `ADMIN`
- `WAITER`
- `KITCHEN`
- `CASHIER`

olabilir.

Gerçek roller mevcut kod üzerinden doğrulanmalıdır.

Örnek prensip:

`WAITER` token:

`/api/admin/users`

endpointine erişememelidir.

`KITCHEN`:

yalnızca mutfağın gerçekleştirmesi gereken işlemleri yapabilmelidir.

`WAITER`:

yalnızca garsonun gerçekleştirmesi gereken işlemleri yapabilmelidir.

`ADMIN`:

tanımlanmış yönetim yetkilerine sahip olabilir.

Role kuralları merkezi ve reusable şekilde yönetilmelidir.

---

# 14. Masa Oturum Güvenliği ve Troll Sipariş Engelleme

Bu mevcut projenin KRİTİK business/security kuralıdır.

Yeni authentication veya QR session refactoru bu kuralı sessizce kaldıramaz.

## Temel Troll Senaryosu

Eğer masadaki dinamik QR yalnızca ilk okumada uzun süreli yetki verirse:

1. Kötü niyetli kullanıcı boş masaya gelir.
2. QR'ı okutur.
3. Mekândan ayrılır.
4. Daha sonra gerçek müşteriler masaya oturur.
5. Eski kullanıcı evinden o masaya sipariş gönderebilir.

Bu senaryo engellenmelidir.

## BOS → DOLU İlk Sipariş Doğrulaması

Masa `BOS` ise:

- Menü incelemek serbest olabilir.
- Session henüz committed olmayabilir.

Ancak masadan İLK sipariş verilirken ve masa:

`BOS → DOLU`

geçişi yaparken, sipariş API'si müşteriden o anda geçerli fiziksel QR/TOTP
doğrulaması istemelidir.

Amaç:

İlk siparişi veren kişinin o anda fiziksel olarak masada bulunduğunu
kanıtlamak ve eski QR bağlantılarını geçersiz hale getirmektir.

## DOLU Masada Arkadaş Katılımı

Masa zaten `DOLU` ise ve aktif/committed masa oturumu varsa:

Masaya sonradan gelen kullanıcının QR okutması onu mevcut doğrulanmış masa
grubuna katabilir.

Bu kullanıcıların her siparişte yeniden QR okutması zorunlu olmamalıdır.

Temel business kuralı:

> Sadece boş masayı ilk sipariş ile sahiplenen kişi güncel fiziksel QR/TOTP
> doğrulaması yapmak zorundadır.

Yeni customer-session authentication mimarisi bu mevcut kural ile uyumlu
tasarlanmalıdır.

Bu davranışın değiştirilmesi gerekiyorsa kullanıcı onayı alınmalıdır.

---

# 15. QR / Customer Session Güvenliği

QR customer authentication/session implementasyonu
`docs/SECURITY_AUTH_REFACTOR.md` gereksinimlerine uygun olmalıdır.

Genel prensip:

```text
QR / TOTP / secure bootstrap
→ Backend validation
→ Customer session
→ Session token
→ Protected customer operations
```

Client tarafından gönderilen yalnızca:

`?masa=5`

gibi bilgi authentication olarak kabul edilmemelidir.

Customer session'ın hangi masaya ait olduğu backend tarafından bilinmelidir.

Mümkün olduğunda request'teki table ID yerine authenticated session'ın
table ID bilgisi kullanılmalıdır.

Session token:

- tahmin edilmesi kolay olmamalı,
- expire edilebilmeli,
- revoke edilebilmeli,
- server tarafından doğrulanabilmelidir.

---

# 16. Staff Authentication

Garson, mutfak, kasa ve admin için kullanılan authentication mekanizması
mevcut backend teknolojisine uygun şekilde uygulanmalıdır.

Staff authentication customer QR session authentication ile karıştırılmamalıdır.

Genel prensip:

```text
username/password
→ backend credential validation
→ staff access token/session
→ protected staff API
```

Eğer JWT kullanılıyorsa:

- imza doğrulanmalı,
- expiration doğrulanmalı,
- token type doğrulanmalı,
- gerekli minimum claimler kullanılmalıdır.

Örneğin:

- `sub`
- `role`
- `type`
- `exp`

Password hiçbir zaman plain text saklanmamalıdır.

Uygun password hashing mekanizması kullanılmalıdır.

---

# 17. Customer ve Staff Token Ayrımı

Müşteri session tokenı ile personel authentication tokenı birbirinden
ayırt edilmelidir.

Örneğin:

- `STAFF`
- `CUSTOMER_SESSION`

gibi token/session type kullanılabilir.

Bir `CUSTOMER_SESSION` tokenı ile:

- admin,
- waiter,
- kitchen,
- cashier

staff endpointlerine erişilememelidir.

Aynı şekilde staff tokenının customer table session yetkisi varmış gibi
otomatik davranmasına izin verilmemelidir.

---

# 18. Multiple Device / Multiple User

Aynı masaya birden fazla cihaz bağlanabileceği varsayılmalıdır.

Sistem şu senaryoyu güvenli şekilde destekleyebilmelidir:

```text
Table 5
├── Session A
├── Session B
└── Session C
```

Bu sessionlar:

- aynı masaya ait olabilir,
- farklı cihazlara ait olabilir,
- kendi authentication/session identifierlarına sahip olabilir.

Business behavior açık şekilde tanımlanmalıdır:

- cart ortak mı?
- cart ayrı mı?
- active order ortak mı?
- ödeme sonrası diğer cihazlar ne görür?
- session nasıl expire olur?
- session nasıl revoke olur?
- aynı anda iki sipariş gelirse ne olur?
- race condition oluşabilir mi?

Mevcut behavior değiştirilecekse ilgili karar dokümante edilmelidir.

---

# 19. Order ve Object-Level Authorization

Sipariş, masa ve benzeri resource endpointlerinde yalnızca ID bilmek erişim
yetkisi anlamına gelmez.

Örneğin:

```text
/orders/10
/orders/11
/orders/12
```

ID değiştirilerek başka resource'a yetkisiz erişilememelidir.

ID'yi UUID yapmak tek başına security çözümü değildir.

Backend her kritik resource operation için doğrulamalıdır:

- authenticated actor kim?
- hangi role sahip?
- hangi table/session'a ait?
- bu resource'a erişme yetkisi var mı?
- bu operation'ı yapma yetkisi var mı?

---

# 20. Order State Transition Kuralları

Order status değişiklikleri yalnızca frontend butonları üzerinden kontrol
edilmeyecektir.

Backend tarafında state transition doğrulaması yapılmalıdır.

Örneğin mevcut business kurallarına göre:

`KITCHEN`:

```text
PAID
→ PREPARING
→ READY
```

`WAITER`:

```text
READY
→ DELIVERED
```

gibi akış bulunabilir.

Gerçek status değerleri mevcut projeden doğrulanmalıdır.

Mantıksız transitionlar:

```text
DELIVERED
→ PREPARING
```

gibi işlemler backend tarafından reddedilmelidir.

Transition kuralları mümkün olduğunca merkezi bir yapı ile yönetilmelidir.

---

# 21. Enum Kullanımı

Finite type/status/role alanlarında uygun olduğunda Enum kullanılmalıdır.

Örneğin:

- `UserRole`
- `OrderStatus`
- `PaymentStatus`
- `SessionType`
- `UserType`

Mevcut projedeki gerçek değerleri incelemeden körü körüne yeni enum oluşturma.

Amaç:

- magic string kullanımını azaltmak,
- typo riskini düşürmek,
- merkezi değişiklik sağlamak,
- API / domain / DB tutarlılığı sağlamaktır.

---

# 22. Yazılım Mimarisi ve Responsibility Separation

Kodda net sorumluluk sınırları tercih edilmelidir.

Çok büyük ve birbirinden bağımsız sorumluluklar taşıyan dosyalardan
kaçınılmalıdır.

Mümkün olduğunca şu ayrımlar korunmalıdır:

- controllers / routers
- services
- repositories
- database/domain models
- request DTOs / schemas
- response DTOs / schemas
- authentication
- authorization
- middleware / dependencies / filters
- enums
- WebSocket / realtime services

Gereksiz abstraction oluşturma.

Sadece mimari daha karmaşık görünsün diye ekstra layer ekleme.

---

# 23. Controller / Service / Repository Katmanları

Kod yapısı mümkün olduğunca:

```text
Controller / Router / API
→ Service / Business Logic
→ Repository / Data Access
→ Database
```

şeklinde ayrılmalıdır.

Katmanlar arasındaki dependency mümkün olduğunda Dependency Injection
üzerinden yönetilmelidir.

Business logic doğrudan controller içine gömülmemelidir.

Controller mümkün olduğunca yalnızca:

- request alma,
- request validation,
- authentication/authorization dependency kullanma,
- service çağırma,
- uygun response döndürme

sorumluluklarını taşımalıdır.

---

# 24. DTO / Response Kuralları

API response olarak doğrudan database entity döndürülmeyecektir.

Internal/domain/database modelleri ile dış API response modelleri ayrılmalıdır.

Örneğin:

```text
Order DB Model
→ OrderService
→ OrderResponse DTO
→ Controller Response
```

Sadece client'ın gerçekten ihtiyaç duyduğu alanlar response içinde bulunmalıdır.

Amaç:

- hassas internal field'ların sızmasını engellemek,
- API contract'ını database modelinden ayırmak,
- future refactorları kolaylaştırmaktır.

---

# 25. Dosya Uzunluğu ve Sorumluluk

Bir dosya çok fazla farklı responsibility taşıyorsa bölünmelidir.

Ancak yalnızca satır sayısı fazla diye anlamsız fragmentation yapılmamalıdır.

Bölme kararı responsibility üzerinden verilmelidir.

Örneğin tek bir `schemas.py` içerisinde tüm projenin:

- admin,
- waiter,
- kitchen,
- order,
- auth,
- payment

schema'larının binlerce satır halinde tutulmasından kaçınılmalıdır.

---

# 26. Mobil ve Arayüz Performans Kuralları

QR Menü ve Garson Panelinde mobil performans görsel süslemeden daha önemlidir.

Hedef:

- hızlı rendering,
- düşük GPU kullanımı,
- mümkün olduğunca akıcı 60 FPS deneyim,
- lightweight UI.

---

# 27. Yasaklı Ağır CSS Efektleri

## `backdrop-filter` / blur YASAĞI

Hiçbir:

- navbar,
- kart,
- modal,
- panel,
- menu

üzerinde:

```css
backdrop-filter: blur(...);
```

ve benzeri ağır blur efektleri kullanılmayacaktır.

Bunun yerine yüksek opaklıklı sade arka planlar kullanılabilir.

Örneğin:

```css
background: rgba(11, 15, 25, 0.95);
```

## `background-attachment: fixed` YASAĞI

Mobil scroll sırasında yüksek repaint maliyeti nedeniyle kullanılmayacaktır.

## Ağır Canlı Radyal Gradient YASAĞI

Sürekli repaint gerektiren karmaşık arka plan efektlerinden kaçınılacaktır.

## `transition: all` YASAĞI

Şu kullanım yasaktır:

```css
transition: all;
```

Yalnızca gerçekten animasyon yapılacak property belirtilmelidir.

Örneğin:

```css
transition: transform 0.15s ease, opacity 0.15s ease;
```

## Ağır Glow / Multi-layer Shadow YASAĞI

Çok katmanlı ağır `box-shadow` ve glow efektleri kullanılmayacaktır.

Tercih:

- border,
- hafif shadow,
- sade contrast.

---

# 28. Frontend Rendering Performansı

DOM güncellemelerinde mümkün olduğunca sadece değişen elementler
güncellenmelidir.

Her küçük değişiklikte tüm listeyi:

```javascript
element.innerHTML = ...
```

ile sıfırdan oluşturmak gibi gereksiz full re-render işlemlerinden
kaçınılmalıdır.

Görseller:

- WebP,
- uygun resolution,
- mobil cihazlara uygun boyut

ile kullanılmalıdır.

---

# 29. Browser Native Popup YASAĞI

Aşağıdaki browser popup API'leri UI içinde kullanılmayacaktır:

- `alert()`
- `confirm()`
- `prompt()`

Tüm:

- uyarılar,
- doğrulamalar,
- confirmation işlemleri,
- kullanıcı mesajları

uygulama içi özel component/modal/toast üzerinden yapılmalıdır.

Örneğin:

- `showCustomConfirm`
- `showToast`
- `showAdminToast`

veya mevcut proje component sistemi kullanılabilir.

UI mevcut koyu tema ve performans kurallarına uygun olmalıdır.

---

# 30. Database ve SQL Kuralları

## Kod İçine SQL Migration / DDL Gömme YASAĞI

Python/backend business kodu içerisine doğrudan:

- `CREATE TABLE`
- `ALTER TABLE`
- `DROP TABLE`
- schema migration
- ad-hoc migration DDL

gömülmeyecektir.

Database schema değişikliği gerekiyorsa:

1. İhtiyaç gerçek kod üzerinden analiz edilir.
2. Gerekli değişiklik kullanıcıya açıklanır.
3. Gerekli SQL açık şekilde hazırlanır.
4. `docs/IMPLEMENTATION_STATUS.md` içine required manual action / blocker olarak kaydedilir.
5. Kullanıcı onayı olmadan database schema değişikliği uygulanmaz.

Agent autonomous çalışıyor olsa bile bu kural geçerlidir.

Kullanıcı database değişikliğini onayladıktan sonra bile yapılan değişiklik
`docs/CODEX_CHANGELOG.md` içinde kaydedilmelidir.

---

# 31. SQL / Enum / Type Tutarlılığı

DB/domain/API katmanlarında finite status/type değerlerinin mümkün olduğunca
tutarlı yönetilmesi gerekir.

Enum kullanımı değerlendirirken:

- Python/domain type
- Pydantic/API schema
- database representation

arasındaki uyumu kontrol et.

Ancak gereksiz generic abstraction oluşturma.

Basit problem için karmaşık generic framework yazma.

---

# 32. Dependency ve Infrastructure Politikası

Sırf modern veya popüler olduğu için projeye büyük dependency eklenmeyecektir.

Özellikle:

- Redis
- RabbitMQ
- Kafka
- external message broker
- distributed cache
- gereksiz microservice altyapısı

doğrudan eklenmeyecektir.

Önce:

1. Mevcut mimari incelenmeli.
2. Gerçek ihtiyaç belirlenmeli.
3. Basit çözümün neden yetersiz olduğu gösterilmeli.
4. Kullanıcıya öneri sunulmalıdır.

Mevcut proje için:

```text
single backend + database + WebSocket
```

yeterliyse sırf teknoloji kullanmış olmak için RabbitMQ/Kafka eklenmemelidir.

Yeni önemli infrastructure dependency öneriliyorsa:

- gerekçe açıklanmalı,
- trade-off açıklanmalı,
- `docs/IMPLEMENTATION_STATUS.md` içine architectural decision olarak yazılmalı,
- kullanıcı onayı olmadan eklenmemelidir.

---

# 33. Session Storage Kararları

Session storage seçimi bilinçli yapılmalıdır.

Aşağıdaki seçenekler ihtiyaca göre değerlendirilmelidir:

- process memory
- database-backed session
- Redis

Sadece process memory kullanılırsa:

```text
Server restart
→ session kaybı
```

Birden fazla backend instance:

```text
Backend A session oluşturdu
→ Backend B session'ı bilmeyebilir
```

problemleri dikkate alınmalıdır.

Staj projesi için database-backed session yeterliyse sırf production-scale
mimari görünümü için Redis eklenmemelidir.

---

# 34. WebSocket / Realtime Security

WebSocket frontend güvenlik sınırı değildir.

WebSocket bağlantıları için gerektiğinde:

- authentication,
- authorization,
- room/session ownership,
- table ownership,
- staff role kontrolü

uygulanmalıdır.

Her client tüm realtime event'leri almamalıdır.

Örneğin `Table 5` session'ı:

`Table 6`

özel realtime eventlerini görmemelidir.

Staff role'leri de yalnızca izin verilen event/channel verilerine
erişebilmelidir.

Mevcut WebSocket implementasyonu değiştirilmeden önce:

- connection nerede açılıyor,
- connection nasıl kapanıyor,
- reconnect nasıl oluyor,
- eventler nerede publish ediliyor,
- clientlar nasıl subscribe oluyor,
- authentication uygulanıyor mu

incelenmelidir.

---

# 35. RabbitMQ / Kafka / Event-Driven Değerlendirmesi

RabbitMQ, Kafka ve WebSocket aynı problem için kullanılan teknolojiler
olarak kabul edilmemelidir.

Agent mevcut sistemi inceleyerek gerektiğinde açıklamalıdır:

- WebSocket ne işe yarıyor?
- RabbitMQ ne işe yarıyor?
- Kafka ne işe yarıyor?
- Aralarındaki fark nedir?
- Mevcut proje gerçekten message broker gerektiriyor mu?
- Tek backend + WebSocket yeterli mi?
- Birden fazla backend instance çalışırsa ne değişir?

Sadece mimari daha profesyonel görünsün diye RabbitMQ/Kafka eklenmemelidir.

---

# 36. Automated Security Testing

Security-sensitive değişikliklerde mümkün olduğunda automated test
eklenmelidir.

Özellikle negative tests önemlidir.

Test edilmesi gereken örnek senaryolar:

- missing token
- invalid token
- expired token
- wrong role
- `CUSTOMER_SESSION` token → STAFF endpoint
- `WAITER` token → ADMIN endpoint
- wrong table/session
- unauthorized order ID
- invalid order state transition
- manipulated price
- manipulated total
- manipulated table ID
- invalid session
- revoked session

Normal UI flow'un çalışması tek başına security test sayılmaz.

---

# 37. Manual HTTP Security Testing

Security refactor sonrasında mümkün olduğunda manuel verification
senaryoları da açıklanmalıdır.

Frontend bypass edilerek API davranışı test edilebilir.

Örneğin:

- DevTools
- curl
- Postman
- direct `fetch()`

kullanılabilir.

Ama test yalnızca proje sahibinin kendi geliştirme ortamı ve sistemi üzerinde
yapılacaktır.

Amaç:

Backend'in frontend olmadan da güvenlik kurallarını enforce ettiğini
doğrulamaktır.

---

# 38. Security Audit

Mevcut proje gerektiğinde aşağıdaki başlıklarda kontrol edilmelidir:

- authentication eksik endpoint
- authorization eksik endpoint
- IDOR / object-level authorization
- role bypass
- client-controlled price
- client-controlled total
- client-controlled table ID
- client-controlled status
- insecure QR token
- predictable token
- session expiration
- session revocation
- password storage
- JWT validation
- WebSocket authentication
- sensitive data exposure
- validation eksikleri
- SQL injection riski
- duplicate/concurrent order işlemleri
- race condition
- CORS'un authentication yerine yanlış kullanılması

Bulunan security finding'ler mümkün olduğunda:

- `CRITICAL`
- `HIGH`
- `MEDIUM`
- `LOW`

severity seviyelerinden biriyle kaydedilmelidir.

Security finding'ler `docs/IMPLEMENTATION_STATUS.md` içinde kayıt altına
alınmalıdır.

---

# 39. Documentation Synchronization

Kod değiştiğinde ilgili dokümantasyon aynı çalışma oturumunda güncellenmelidir.

Özellikle şu alanlar değiştiğinde dokümantasyon kontrol edilmelidir:

- authentication flow
- authorization flow
- endpoints
- roles
- QR behavior
- customer session behavior
- TOTP behavior
- database models
- order status transitions
- WebSocket architecture
- multiple-device behavior
- security findings

Dokümantasyon bilerek obsolete bırakılmamalıdır.

---

# 40. Kullanıcı Onayı Gerektiren Değişiklikler

Aşağıdaki önemli değişiklikler kullanıcı onayı olmadan uygulanmamalıdır:

- database schema / migration değişiklikleri,
- önemli business-rule değişiklikleri,
- TOTP masa güvenliği paradigmasının değiştirilmesi,
- authentication modelinin temel olarak değiştirilmesi,
- önemli API contract'ını breaking şekilde değiştirmek,
- çalışan önemli behavior'ı kaldırmak,
- Redis / RabbitMQ / Kafka gibi önemli infrastructure dependency eklemek,
- mevcut güvenlik requirement'ını zayıflatmak.

Böyle bir ihtiyaç ortaya çıkarsa:

1. Teknik nedeni doğrula.
2. `docs/IMPLEMENTATION_STATUS.md` içinde kaydet.
3. Önerilen çözümü açıkla.
4. Gerekirse işi blocker olarak işaretle.
5. Kullanıcı onayı bekle.

---

# 41. Completion Rule

Bir task yalnızca kod yazıldığı için tamamlanmış değildir.

Bir task `COMPLETE` sayılabilmek için:

- implementation tamamlanmış olmalı,
- ilgili gerçek kod incelenmiş olmalı,
- gerekli testler çalıştırılmış olmalı,
- test sonuçları gerçek şekilde raporlanmış olmalı,
- failures belgelenmiş olmalı,
- `docs/IMPLEMENTATION_STATUS.md` güncel olmalı,
- `docs/CODEX_CHANGELOG.md` güncel olmalı,
- unresolved work açıkça yazılmış olmalı,
- exact next action güncel olmalı.

Security milestone'ları verification olmadan `COMPLETE` olarak
işaretlenemez.

---

# 42. Final Agent Davranışı ve Açıklanabilirlik

AI agent'ın amacı yalnızca çalışan kod üretmek değildir.

Kodun:

- neden bu şekilde tasarlandığını,
- authentication'ın nasıl çalıştığını,
- authorization'ın nerede uygulandığını,
- session'ın nasıl çalıştığını,
- token'ın nasıl doğrulandığını,
- JWT kullanılıyorsa imzanın ne sağladığını,
- role kontrolünün nerede yapıldığını,
- service authorization'ın neden ayrıca gerekli olduğunu,
- WebSocket'in nasıl çalıştığını,
- multiple-user senaryosunun nasıl yönetildiğini,
- hangi security açıklarının kapatıldığını

anlaşılır şekilde açıklayabilmesi gerekir.

Özellikle AI tarafından yazılmış kodlarda:

> Çalışıyor.

tek başına yeterli kabul edilmez.

Kodun amacı, sorumlulukları, güvenlik modeli ve mimarisi anlaşılabilir olmalıdır.