# Security, Authentication and Architecture Refactor

## Amaç

Bu dosya QR Menü projesinin authentication, authorization, session yönetimi,
endpoint güvenliği, role-based access control, DTO/schema düzeni, enum yapısı,
WebSocket güvenliği ve ilgili mimari iyileştirmeleri için ana gereksinim
dokümanıdır.

Codex ilgili alanlarda çalışmadan önce bu dosyayı okumalıdır.

Bu dosya:

- NE yapılacağını tanımlar.

İlerleme durumu:

- `IMPLEMENTATION_STATUS.md`

dosyasında tutulur.

Gerçek kod değişikliklerinin geçmişi:

- `CODEX_CHANGELOG.md`

dosyasında tutulur.

Bu dosyadaki gereksinimler yalnızca implementasyonu mevcut koda uydurmak
amacıyla sessizce değiştirilmemelidir.

Bir gereksinimin teknik olarak değiştirilmesi gerekiyorsa sebebi önce
`IMPLEMENTATION_STATUS.md` içerisinde belgelenmelidir.

---

# Gereksinimler
Mevcut QR menü / sipariş / ödeme projem üzerinde authentication, authorization, session yönetimi, endpoint güvenliği, enum/DTO düzeni ve real-time mimarisini iyileştirmeni istiyorum.

ÖNEMLİ:
- Önce mevcut projeyi baştan sona incele.
- Kullanılan framework, mevcut controller/service/repository yapısı, modeller, endpointler, authentication varsa mevcut hali, QR akışı ve WebSocket/socket yapısını analiz et.
- Mevcut çalışan akışı gereksiz yere bozma.
- Doğrudan büyük bir refactor yapmadan önce mevcut durum + yapılacak değişiklikler için kısa bir plan çıkar.
- Sonra değişiklikleri mantıklı aşamalara bölerek uygula.
- Her aşamanın sonunda ne değiştirdiğini ve neden yaptığını açıkla.
- AI tarafından daha önce yazılmış kodları körü körüne koruma; güvenlik ve mimari açısından kontrol et.
- Gereksiz dependency veya gereksiz karmaşık teknoloji ekleme.

==================================================
1. ENUM YAPISI
==================================================

Projede string/int olarak dağınık kullanılan tip, rol ve durum değerlerini Enum yapısına geçir.

Örnek kategoriler:
- UserRole
  - ADMIN
  - WAITER
  - KITCHEN
  - CASHIER
- OrderStatus
- PaymentStatus
- UserType
- gerekiyorsa SessionType
- projede bulunan diğer sabit tip/durum alanları

Ama mevcut projedeki gerçek değerleri önce incele ve ona göre enumları oluştur.

Amaç:
- "magic string" kullanımını azaltmak
- typo riskini engellemek
- değer değiştirildiğinde merkezi bir yerden değiştirilebilmesini sağlamak

Enumları uygun ortak klasör/dosyalarda tut.

==================================================
2. MODEL / SCHEMA / DTO / RESPONSE AYRIMI
==================================================

Mevcut dosya yapısını incele.

Çok uzun dosyalar varsa sorumluluklarına göre böl.

Bir dosya birden fazla alakasız sorumluluk taşımamalı.

Örneğin mümkün olduğunca şu ayrımı koru:

- database/domain models
- request schemas / DTO
- response schemas / DTO
- enums
- controllers / routers
- services
- repositories
- authentication / authorization
- filters / middleware / dependencies

DB modelini doğrudan controller response olarak döndürmek yerine uygun Response DTO / Schema kullan.

Örneğin:
Order DB Model
→ OrderService
→ OrderResponse DTO
→ Controller

Internal alanların istemciye gereksiz yere dönmesini engelle.

Bütün schema/model sınıflarını tek bir dev dosyada toplama.
Domain veya feature bazlı ayır.

Örneğin:
orders/
auth/
waiter/
kitchen/
cashier/
admin/
menu/
common/

Mevcut projenin mimarisine uygun isimlendirme kullan; sırf bu örneği birebir uygulamak zorunda değilsin.

==================================================
3. QR MÜŞTERİ AUTHENTICATION / SESSION
==================================================

QR üzerinden gelen müşteriler için güvenli session tabanlı authentication oluştur.

Mevcut QR akışını önce incele.

Ama hedef mimari şu:

QR okutulur
→ QR içerisindeki güvenli token/code backend'e gönderilir
→ Backend tokenı doğrular
→ Bunun hangi masaya ait olduğunu backend belirler
→ Customer Session oluşturulur
→ Client'a güvenli bir session/access token verilir
→ Sonraki müşteri istekleri bu token ile authenticate edilir

Müşterinin yalnızca:

?masa=5

gibi bir parametre göndermesine güvenme.

QR token:
- tahmin edilmesi kolay olmamalı
- cryptographically secure olmalı
- mümkünse DB'de raw token yerine hash tutulmasını değerlendir
- expire/revoke edilebilmeli
- hangi masa için oluşturulduğu backend tarafından bilinmeli

CustomerSession yapısında ihtiyaca göre:
- id
- table_id
- token_hash veya güvenli session identifier
- created_at
- expires_at
- revoked_at / active
- gerekiyorsa device/session metadata

tutulabilir.

Cart'ın session içinde mi yoksa DB'de ayrı tutulmasının daha doğru olduğunu mevcut mimariye göre değerlendir.

Tercihen business data (cart/order) yalnızca process-memory içerisinde tutulmasın.
Server restart ve birden fazla backend instance senaryosunu düşün.

==================================================
4. MASA ID'SİNE CLIENT'TAN GÜVENME
==================================================

Şu an özellikle masa/sipariş endpointlerini incele.

Örneğin bunun gibi bir endpoint varsa:

GET /api/masalar/{masa_id}/aktif-siparis

istemci path'teki masa id'sini değiştirerek başka masanın verisini görebiliyor olabilir.

Ben manuel testte masa ID'sini değiştirerek başka masaların aktif sipariş bilgilerini okuyabildim.

Bu problemi düzelt.

Customer session token hangi masaya aitse erişim ona göre belirlensin.

Mümkünse müşteri endpointlerinde masa ID'sinin client tarafından verilmesini tamamen kaldır.

Örneğin:

GET /api/customer/active-order
Authorization: Bearer <customer-session-token>

Backend:
token → session → table_id

şeklinde çalışabilir.

Eğer mevcut endpoint yapısı nedeniyle masa_id URL'de kalacaksa:

requested_table_id == authenticated_session.table_id

kontrolü zorunlu olsun.

Client'ın table_id değerine güvenme.

==================================================
5. STAFF AUTHENTICATION
==================================================

Garson, mutfak, kasa ve admin kullanıcıları için ayrı personel authentication akışını incele ve güvenli hale getir.

Mentor notumda "CWP(?)" şeklinde duyduğum bir ifade var. Bunun JWT olması muhtemel fakat bunu varsayarak körü körüne implement etme.

Mevcut backend teknolojisine uygun authentication mekanizmasını seç.

Beklentim genel olarak:

username/password
→ backend login endpoint
→ credentials doğrulanır
→ access token oluşturulur
→ sonraki requestlerde token HTTP Authorization header üzerinden gönderilir

Örneğin:

Authorization: Bearer <token>

JWT kullanılması uygunsa token içerisinde minimum gerekli claimleri tut:

- user id / sub
- role
- exp
- gerekiyorsa token/session type

Örneğin:
{
  "sub": "42",
  "role": "WAITER",
  "type": "STAFF",
  "exp": ...
}

Passwordleri plain text saklama.
Uygun password hashing mekanizmasını kullan.

Basic Authentication'ın projede anlamlı olduğu bir yer varsa değerlendir ve nedenini açıkla.
Ancak credentials'ın her API requestinde sürekli gönderilmesini gerektiren zayıf bir tasarım yapma.

==================================================
6. AUTHENTICATION FILTER / MIDDLEWARE
==================================================

Controller endpointlerine doğrudan herkesin HTTP request atmasını engelle.

Request akışı mümkün olduğunca:

HTTP Request
→ Authentication Filter / Middleware / Dependency
→ token validation
→ Authorization
→ Controller
→ Service
→ Repository
→ DB

şeklinde olsun.

Authentication katmanında:
- token var mı?
- token formatı doğru mu?
- imzası / session değeri geçerli mi?
- expire olmuş mu?
- revoke edilmiş mi?
- token type doğru mu?

kontrol edilsin.

Bu kontrolü her controller içinde kopyala-yapıştır şekilde yazma.
Reusable filter/dependency/middleware oluştur.

Framework'ün tavsiye ettiği yöntemi kullan.

==================================================
7. ROLE-BASED AUTHORIZATION
==================================================

Token/session içerisine personel rolünü dahil et ve Role-Based Access Control uygula.

Örnek:

ADMIN
WAITER
KITCHEN
CASHIER

Garson tokenı ile admin endpointlerine erişilememeli.

Örneğin:

WAITER token
→ GET /api/admin/users
→ 403 Forbidden

KITCHEN kullanıcısı yalnızca mutfakla ilgili işlemleri yapabilmeli.

WAITER yalnızca garsona ait işlemleri yapabilmeli.

ADMIN gerekli yönetim işlemlerini yapabilmeli.

Reusable bir yapı oluştur.

Örneğin konsept olarak:

require_roles(ADMIN, WAITER)

gibi kullanılabilsin.

Mevcut projeye göre endpoint → izin matrisi oluştur ve hangi rolün hangi endpointlere erişebileceğini belirle.

==================================================
8. AUTHENTICATION VE AUTHORIZATION'I AYIR
==================================================

Authentication:
"Bu requesti atan kişi kim?"

Authorization:
"Bu kişi bu işlemi yapabilir mi?"

Bunları ayrı düşün.

Örneğin:
- geçerli WAITER tokenı var
- fakat ADMIN endpointine erişmeye çalışıyor

Bu durumda token geçerli olsa bile:
403 Forbidden

Token hiç yoksa veya invalid ise:
401 Unauthorized

==================================================
9. ORDER ENDPOINT GÜVENLİĞİ
==================================================

Sipariş controller ve service katmanlarını özellikle incele.

Şu anda frontend'i hiç kullanmadan HTTP request oluşturarak siparişleri ID/index üzerinden seçip durumlarını değiştirebildiğim senaryolar var.

Örneğin saldırgan şunu yapabiliyor olmamalı:

PATCH /orders/10/status
PATCH /orders/11/status
PATCH /orders/12/status

ve yalnızca ID değiştirerek farklı siparişlerde işlem yapmamalı.

ID'nin tahmin edilebilir olmaması tek çözüm değil.
UUID eklemek authorization'ın yerine geçmez.

Her kritik object operation için backend:
- authenticated user/session kim?
- hangi role sahip?
- bu object'e erişim yetkisi var mı?
- bu değişikliği yapmaya yetkisi var mı?

kontrol etmeli.

==================================================
10. ORDER STATUS BUSINESS RULES
==================================================

Yalnızca endpoint rol kontrolü yapmak yeterli değil.

Role göre yapılabilecek status değişikliklerini service katmanında da doğrula.

Örneğin mevcut projeye uygun şekilde:

KITCHEN:
- PAID → PREPARING
- PREPARING → READY

WAITER:
- READY → DELIVERED

ADMIN:
- gerekiyorsa daha geniş yetki

Bu sadece örnek; mevcut status akışını projeden çıkar.

Geçersiz state transitionları reddet.

Örneğin:

DELIVERED → PREPARING

normal business flow içinde mümkün olmamalı.

Order status transition için merkezi bir yapı/state machine/transition map oluşturmayı değerlendir.

==================================================
11. CLIENT'TAN GELEN BUSINESS-CRITICAL VERİLERE GÜVENME
==================================================

Sipariş oluştururken veya güncellerken client'ın gönderdiği kritik değerlere güvenme.

Özellikle incele:

- table_id
- price
- total
- payment_status
- order_status
- role
- user id / ownership bilgileri

Örneğin müşteri:

{
  "product_id": 25,
  "quantity": 2
}

gönderebilir.

Ama fiyat:
DB'deki Product üzerinden backend tarafından alınmalı.

Total:
backend tarafından hesaplanmalı.

table_id:
authenticated customer session'dan alınmalı.

order status:
business logic tarafından belirlenmeli.

Client'ın:
price = 1
status = DELIVERED
role = ADMIN

gibi değerler göndermesi backend tarafından güvenilir kabul edilmemeli.

Mevcut `process_order_items` vb. fonksiyonları bu açıdan incele.

==================================================
12. CUSTOMER TOKEN VE STAFF TOKEN'I AYIR
==================================================

Müşteri QR session tokenı ile personel authentication tokenını birbirinden ayır.

Örneğin token type konsepti kullanılabilir:

STAFF
CUSTOMER_SESSION

Müşteri tokenı ile:
- admin
- waiter
- cashier
- kitchen

endpointlerine erişilememeli.

Personel tokenının da müşteri sessionı gibi davranmasına izin verilmemeli.

==================================================
13. MULTIPLE USER / MULTIPLE DEVICE SENARYOSU
==================================================

Aynı masa QR kodunu birden fazla telefon okutursa sistemin nasıl davranacağını incele ve tanımla.

Tercihen:

Table 5
- Session A
- Session B
- Session C

gibi birden fazla customer session desteklenebilir.

Her cihazın/session'ın kendi tokenı olabilir ama hepsi aynı table_id ile ilişkilendirilebilir.

Şunları değerlendir:
- aynı masada birden fazla kullanıcı aynı anda sipariş verebilir mi?
- cart ortak mı ayrı mı?
- active order ortak mı?
- session expire/revoke nasıl olacak?
- ödeme yapıldığında diğer cihazlar nasıl bilgilendirilecek?
- eş zamanlı değişikliklerde race condition oluşabilir mi?

Mevcut business gereksinimlerine en uygun tasarımı öner ve uygula.

==================================================
14. SOCKET / WEBSOCKET MİMARİSİNİ İNCELE
==================================================

Projede gerçek zamanlı akış mevcut veya planlı:

Müşteri ödeme yapar
→ mutfak siparişi görür

Mutfak:
PREPARING / READY

Garson:
DELIVERED

Müşteri ekranı da status değişikliklerini real-time görür.

Mevcut projede WebSocket/socket kodunun:
- hangi dosyalarda olduğunu
- connection'ın nerede açıldığını
- eventlerin nasıl yayınlandığını
- hangi clientların hangi eventleri aldığını
- connection authentication olup olmadığını
- disconnect/reconnect mantığını

incele ve bana açıkla.

AI tarafından daha önce yazılan socket kodunun tam olarak ne yaptığını açıklamanı istiyorum.

Socket bağlantıları authentication/authorization açısından da kontrol edilmeli.
Her client her event'i alamamalı.

==================================================
15. RABBITMQ / KAFKA / EVENT-DRIVEN KONUSUNU DEĞERLENDİR
==================================================

RabbitMQ, Kafka veya başka event/message broker sistemlerini sırf teknoloji eklemek için projeye dahil etme.

Önce mevcut proje ölçeğini değerlendir.

Bana şunları açıkla:

- WebSocket ne işe yarıyor?
- RabbitMQ ne işe yarıyor?
- Kafka ne işe yarıyor?
- Bunların birbirinden farkı ne?
- Benim mevcut projem gerçekten message broker gerektiriyor mu?
- Tek backend + WebSocket yeterli mi?
- Birden fazla backend instance çalışırsa ne değişir?

Gerekmiyorsa projeye RabbitMQ/Kafka ekleme.
Sadece ileride ölçeklenme durumunda nasıl kullanılabileceğini açıkla.

==================================================
16. SESSION STORAGE / MEMORY / DB
==================================================

Authentication/session bilgilerinin nerede tutulduğunu incele.

Sadece process memory kullanılıyorsa şu problemi değerlendir:

Server restart
→ tüm sessionlar kaybolur

Birden fazla backend instance:
Backend A'da oluşturulan session
→ Backend B tarafından bilinmez

Mevcut proje için:
- in-memory
- database-backed session
- Redis

seçeneklerini değerlendir.

Staj projesini gereksiz karmaşıklaştırmadan en mantıklı çözümü kullan.

DB-backed session yeterliyse sırf Redis kullanmış olmak için Redis ekleme.

==================================================
17. SQL / TYPE / GENERIC YAPI
==================================================

SQL modellerinde tekrar eden type/enum tanımlarını incele.

Uygun olan yerlerde generic/reusable yapı oluştur.

Ama gereksiz abstraction yapma.

Enumların:
- Python/domain tarafı
- API schema tarafı
- DB/SQL tarafı

arasında tutarlı çalışmasını sağla.

Migration gerekiyorsa mevcut DB'yi kırmadan yönet.

==================================================
18. SECURITY AUDIT
==================================================

Mevcut projeyi aşağıdaki açılardan incele:

- authentication eksik endpoint
- authorization eksik endpoint
- IDOR / object-level authorization
- role bypass
- client-controlled price
- client-controlled table id
- client-controlled status
- insecure QR token
- tahmin edilebilir token
- session expiration
- session revocation
- password storage
- JWT validation
- WebSocket authentication
- CORS'un authentication yerine yanlış kullanılması
- sensitive data exposure
- validation eksikleri
- SQL injection riski
- duplicate/concurrent order işlemleri
- race condition ihtimali

Gördüğün açıkları severity ile listele:
CRITICAL / HIGH / MEDIUM / LOW

Sonra öncelikli olanları düzelt.

==================================================
19. TESTLER
==================================================

Authentication ve authorization için otomatik testler ekle.

En azından aşağıdaki senaryoları test et:

1.
Token yok
→ protected staff endpoint
→ 401

2.
Geçersiz token
→ protected endpoint
→ 401

3.
Expired token
→ 401

4.
Valid WAITER token
→ ADMIN endpoint
→ 403

5.
Valid ADMIN token
→ ADMIN endpoint
→ başarılı

6.
CUSTOMER_SESSION token
→ ADMIN endpoint
→ reddedilmeli

7.
Session Table 5
→ Table 5 active order
→ başarılı

8.
Session Table 5
→ Table 6 active order
→ reddedilmeli

9.
Token olmadan:
GET /api/masalar/{id}/aktif-siparis
→ protected olması gerekiyorsa reddedilmeli

10.
WAITER:
izin verilen order status transition
→ başarılı

11.
WAITER:
KITCHEN'a ait status transition
→ reddedilmeli

12.
KITCHEN:
READY → DELIVERED
→ reddedilmeli

13.
Invalid order state transition
→ reddedilmeli

14.
Client request içine farklı price/total gönderse bile backend DB fiyatını kullanmalı

15.
Client table_id manipüle etse bile backend authenticated session'daki table_id'yi kullanmalı

==================================================
20. MANUEL HTTP TEST EDİLEBİLİRLİĞİ
==================================================

Frontend hiçbir zaman güvenlik sınırı olarak görülmemeli.

Bir kullanıcı browser DevTools, curl, Postman veya başka bir HTTP client ile frontend'i tamamen bypass edebilir.

Bu nedenle sistem:

"Frontend bu butonu göstermiyor"

mantığına güvenmemeli.

Bütün kritik kurallar backend tarafından enforce edilmeli.

Yaptığın düzeltmelerden sonra bana manuel olarak hangi HTTP requestleri ile authentication/authorization kontrollerini test edebileceğimi de göster.

==================================================
21. ÇIKTI / RAPOR
==================================================

İş bitince bana şu formatta özet ver:

1. Başlangıçta bulduğun mimari
2. Bulduğun güvenlik problemleri
3. Değiştirdiğin dosyalar
4. Eklediğin dosyalar
5. Authentication akışı
6. QR customer session akışı
7. Staff authentication akışı
8. Role authorization yapısı
9. Order authorization/business validation
10. WebSocket mimarisi
11. Multiple-user davranışı
12. Eklediğin testler
13. Hâlâ çözülmemiş / ileride yapılabilecek konular
14. RabbitMQ/Kafka gerekiyor mu, neden?
15. Güvenlik açısından sistem artık hangi saldırıları engelliyor?

ÖNEMLİ:
Kodun sadece çalışması yeterli değil.
Her önemli mimari/güvenlik kararının nedenini de açıkla.

Özellikle benim anlayabileceğim şekilde:
- token nasıl çalışıyor?
- session nasıl çalışıyor?
- filter/dependency ne yapıyor?
- JWT kullanıldıysa imza doğrulama ne sağlıyor?
- role kontrolü nerede yapılıyor?
- service içindeki authorization neden ayrıca gerekli?
- WebSocket nasıl çalışıyor?
- iki kullanıcı aynı anda bağlanınca ne oluyor?

bunları açıklamanı istiyorum.

Önce analiz ve planı göster, ardından implementasyona geç.