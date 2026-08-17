# Proje ve Arayüz Kuralları (AGENTS.md)

Bu dosya, yapay zekanın bu projede ve gelecek geliştirmelerde uyması gereken zorunlu tasarım ve performans kurallarını içerir.

## Mobil ve Arayüz Performans Kuralları (QR Menü & Garson Paneli)

### 1. Yasaklı Ağır CSS Efektleri (Kesinlikle Kullanılmayacak)
* **`backdrop-filter: blur(...)` YASAĞI:** Mobil GPU ve Web View performansını aşırı kastırdığı için hiçbir navbar, kart, modal veya panelde `backdrop-filter` / `blur` kullanılmayacaktır. Bunun yerine yüksek opaklıklı düz/sade renkler (`rgba(11, 15, 25, 0.95)` vb.) kullanılacaktır.
* **`background-attachment: fixed` & Canlı Radyal Gradyan YASAĞI:** Kaydırma (scroll) anında sayfanın sürekli yeniden çizilmesine (repaint) yol açtığı için mobil arka planlarda `fixed` attachment ve karmaşık radyal gradyanlar kullanılmayacaktır.
* **`transition: all` YASAĞI:** Sayfa elemanlarında genel `transition: all` kesinlikle kullanılmayacak; sadece gerekli elemanlara nokta atışı animasyon (`transition: transform 0.15s ease, opacity 0.15s ease`) verilecektir.
* **Çok Katmanlı Ağır Gölgeler (`box-shadow` / Glow):** Mobil ekran kartını yoran ağır glow/parlama ve multi-layer gölgeler yerine sade sınır çizgileri (`border`) veya hafif standart gölgeler tercih edilecektir.

### 2. Performans Odaklı Tasarım Prensibi
* Görsel süslemelerden çok **60 FPS mobil performans ve hız** önceliklidir.
* Arayüzler yavaş/kasan ağır tasarımlar yerine son derece hafif, akıcı, hızlı tepki veren (lightweight) yapıda olacaktır.
* Resimler ve görseller WebP formatında ve mobil ekranlara uygun boyutlandırılmış olarak yüklenecektir.
* DOM güncellemelerinde tüm listeyi sıfırdan re-render etmek (`innerHTML` sıfırlaması) yerine sadece değişen elemanlar güncellenecektir.
