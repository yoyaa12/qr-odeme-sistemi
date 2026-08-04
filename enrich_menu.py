import sys
from app.database import execute_query, execute_non_query, db_transaction

def run_enrichment():
    print("=== MENÜ VE VERİTABANI GÜNCELLEME BAŞLADI ===")
    
    with db_transaction():
        # 1. Ana Yemekler kategorisini ve Izgara Köfte'yi pasife al (silme yok)
        execute_non_query("UPDATE Kategoriler SET aktif_mi = 0 WHERE LOWER(kategori_adi) LIKE '%ana yemek%'")
        execute_non_query("UPDATE Urunler SET aktif_mi = 0 WHERE urun_adi LIKE '%Izgara Köfte%' OR urun_adi LIKE '%Izgara Kofte%'")
        
        # 2. Kategorileri düzenle veya ekle (Türkçe karakterli)
        category_names = [
            'Çorbalar',
            'Pizzalar',
            'Burgerler',
            'Salatalar',
            'Tatlılar',
            'İçecekler',
            'Aperatifler',
            'Soslar'
        ]
        
        cat_map = {}
        existing_cats = execute_query("SELECT id, kategori_adi FROM Kategoriler") or []
        existing_names = {c['kategori_adi'].strip().lower(): c['id'] for c in existing_cats}
        
        for cat_name in category_names:
            key = cat_name.lower()
            alt_keys = [key]
            if key == 'çorbalar': alt_keys.append('corbalar')
            if key == 'tatlılar': alt_keys.append('tatlilar')
            if key == 'içecekler': alt_keys.append('icecekler')
            
            matched_id = None
            for ak in alt_keys:
                if ak in existing_names:
                    matched_id = existing_names[ak]
                    break
            
            if matched_id:
                execute_non_query("UPDATE Kategoriler SET kategori_adi = ?, aktif_mi = 1 WHERE id = ?", (cat_name, matched_id))
                cat_map[cat_name] = matched_id
                print(f"Kategori güncellendi: {cat_name} (ID: {matched_id})")
            else:
                execute_non_query("INSERT INTO Kategoriler (kategori_adi, aktif_mi) VALUES (?, 1)", (cat_name,))
                c_row = execute_query("SELECT id FROM Kategoriler WHERE kategori_adi = ?", (cat_name,), fetch_one=True)
                new_id = c_row['id']
                cat_map[cat_name] = new_id
                print(f"Yeni kategori eklendi: {cat_name} (ID: {new_id})")
                
        # 3. Karışık Pizza'yı Pizzalar kategorisine taşı
        if 'Pizzalar' in cat_map and cat_map['Pizzalar']:
            execute_non_query("UPDATE Urunler SET kategori_id = ? WHERE urun_adi LIKE '%Karışık Pizza%' OR urun_adi LIKE '%Karisik Pizza%'", (cat_map['Pizzalar'],))
        
        # 4. Ürün listesi (Her kategori için 7+ ürün)
        products_data = {
            'Çorbalar': [
                ("Mercimek Çorbası", "Geleneksel lezzet, limon ve kruton ile", 90.0),
                ("Ezogelin Çorbası", "Nane ve tereyağlı sos ile servis edilir", 95.0),
                ("Domates Çorbası", "Kızarmış kruton ekmeği ve rendelenmiş kaşar peyniri ile", 90.0),
                ("Yayla Çorbası", "Taze nane ve tereyağlı süzme yoğurt çorbası", 85.0),
                ("Tarhana Çorbası", "Ev yapımı organik tarhana ve tereyağlı sos", 85.0),
                ("İşkembe Çorbası", "Sarımsak, sirke ve özel acı yağ sosu eşliğinde", 130.0),
                ("Kelle Paça Çorbası", "Yüksek kolajenli, yoğun sarımsak ve sirkeli", 150.0)
            ],
            'Pizzalar': [
                ("Karışık Pizza", "Sucuk, sosis, mantar, mısır, zeytin, kaşar peyniri", 280.0),
                ("Margherita Pizza", "Özel domates sosu, bol mozzarella peyniri, taze fesleğen", 240.0),
                ("Pepperoni Pizza", "Özel pizza sosu, dana pepperoni dilimleri, mozzarella peyniri", 290.0),
                ("Tavuklu Barbekü Pizza", "Izgara tavuk dilimleri, barbekü sos, kırmızı soğan, mısır, mozzarella", 285.0),
                ("Dört Peynirli Pizza", "Mozzarella, parmesan, roquefort, cheddar peynir kombinasyonu", 310.0),
                ("Vejetaryen Pizza", "Kabak, patlıcan, renkli biberler, mantar, zeytin, mısır, mozzarella", 250.0),
                ("Meksika Acılı Pizza", "Acılı kıyma sosu, jalapeño biberi, mısır, kırmızı soğan, mozzarella", 295.0)
            ],
            'Burgerler': [
                ("Klasik Gurme Burger", "150g dana köfte, marul, domates, turşu, karamelize soğan, özel burger sos", 260.0),
                ("Cheeseburger", "150g dana köfte, çift cheddar peyniri, turşu, özel burger sosu", 280.0),
                ("Double Smash Burger", "2x90g smash dana köfte, çift cheddar, çıtır soğan, füme sos", 340.0),
                ("Barbeque Bacon Burger", "150g dana köfte, dana füme kaburga, cheddar, barbekü sos, çıtır soğan", 310.0),
                ("Çıtır Tavuk Burger", "Çıtır panelenmiş tavuk pirzola, lahana salatası (coleslaw), mayonez", 230.0),
                ("Acılı Jalapeño Burger", "150g acılı dana köfte, jalapeño dilimleri, acı sos, cheddar peyniri", 275.0),
                ("Vejetaryen Mantar Burger", "Izgara istiridye mantarı, fırınlanmış biber, avokado sosu", 240.0)
            ],
            'Salatalar': [
                ("Çıtır Tavuklu Sezar Salata", "Yedi renk akdeniz yeşilliği, çıtır tavuk, kruton, parmesan, sezar sos", 210.0),
                ("Akdeniz Salatası", "Yeşillik harmanı, Ezine peyniri, siyah zeytin, ceviz, nar ekşili sos", 180.0),
                ("Ton Balıklı Salata", "Akdeniz yeşillikleri, ton balığı, mısır, kapari, kornişon turşu, limon sos", 230.0),
                ("Izgara Hellim Peynirli Salata", "Izgara hellim peyniri, ızgara sebzeler, ızgara biber, zeytinyağı sos", 220.0),
                ("Gavurdağı Salatası", "İnce kıyım domates, salatalık, kuru soğan, ceviz içi, bol nar ekşisi", 170.0),
                ("Kinoa & Avokadolu Yeşil Salata", "Organik kinoa, avokado dilimleri, taze nane, badem, zeytinyağ limon sos", 240.0),
                ("Roka Parmesan Salatası", "Taze roka yaprakları, çeri domates, kurutulmuş domates, parmesan", 190.0)
            ],
            'Tatlılar': [
                ("Künefe", "Hatay usulü sıcak künefe, özel antep fıstıklı", 160.0),
                ("Fırın Sütlaç", "Geleneksel nar gibi kızarmış fırın sütlaç", 95.0),
                ("Tiramisu", "İtalyan usulü mascarpone peynirli ve espresso lezzeti", 130.0),
                ("San Sebastian Cheesecake", "İçi akışkan kremsi San Sebastian, çikolata sos ile", 170.0),
                ("Sıcak Çikolatalı Souffle", "Akışkan sıcak Belçika çikolatalı sufle", 140.0),
                ("Havuç Dilim Baklava", "Antep fıstıklı havuç dilimi, ılık servis edilir", 190.0),
                ("Antep Fıstıklı Katmer", "Çıtır çıtır taze antep fıstıklı ve kaymaklı katmer", 180.0)
            ],
            'İçecekler': [
                ("Kutu Kola (330ml)", "Soğuk kutu Coca-Cola", 50.0),
                ("Küçük Ayran (200ml)", "Geleneksel yayık ayranı", 35.0),
                ("Büyük Ayran (330ml)", "Cam şişe / büyük boy serinletici ayran", 45.0),
                ("Kutu Fanta (330ml)", "Soğuk kutu Fanta", 50.0),
                ("Kutu Sprite (330ml)", "Soğuk kutu Sprite", 50.0),
                ("Fuse Tea (330ml)", "Şeftali veya Limon aromalı soğuk çay", 50.0),
                ("Şalgam Suyu (330ml)", "Doğal Adana şalgam suyu (Acılı / Acısız)", 40.0),
                ("Ev Yapımı Limonata", "Taze nane yaprakları ile ev yapımı serinletici limonata", 60.0),
                ("Coca-Cola 1L", "1 Litre pet şişe soğuk kola", 85.0),
                ("Fanta 1L", "1 Litre pet şişe soğuk Fanta", 85.0),
                ("Sprite 1L", "1 Litre pet şişe soğuk Sprite", 85.0),
                ("Coca-Cola 1.5L", "1.5 Litre paylaşım boyu soğuk kola", 100.0),
                ("Fanta 1.5L", "1.5 Litre paylaşım boyu soğuk Fanta", 100.0),
                ("Sprite 1.5L", "1.5 Litre paylaşım boyu soğuk Sprite", 100.0)
            ],
            'Aperatifler': [
                ("Patates Kızartması", "Çıtır baharatlı parmak patates kızartması", 80.0),
                ("Baharatlı Elma Dilim Patates", "Özel baharat çeşnili çıtır elma dilim patates", 90.0),
                ("Çıtır Soğan Halkası (12'li)", "Panelenmiş altın sarısı soğan halkaları", 75.0),
                ("Mozzarella Sticks (6'lı)", "İçi uzayan çıtır kaplamalı mozzarella peynir çubukları", 120.0),
                ("Çıtır Tavuk Kovası (10'lu)", "Özel baharatlı panelenmiş kemiksiz tavuk parçaları", 170.0),
                ("Sosis Tabağı & Patates", "Kızartılmış sosisler, patates kızartması ve soslar", 140.0),
                ("Paçanga & Sigara Böreği Tabağı", "Çıtır avcı böreği ve pastırmalı paçanga böreği", 110.0)
            ],
            'Soslar': [
                ("Barbekü Sos", "Tütsülenmiş enfes barbekü sosu", 15.0),
                ("Sarımsaklı Mayonez", "Özel ev yapımı taze sarımsaklı mayonez sos", 15.0),
                ("Ranch Sos", "Yoğurt ve taze yeşillikli zengin dip sos", 20.0),
                ("Acı Chipotle Sos", "Meksika çili biberli hafif tütsülenmiş acı sos", 20.0),
                ("Truffle Mayonez", "Gerçek trüf mantarı aromalı lüks mayonez", 25.0),
                ("Ballı Hardal Sos", "Süzme bal ve hardalın tatlı-keskin uyumu", 20.0),
                ("Tatlı Şili (Sweet Chili) Sos", "Uzak Doğu usulü tatlı acı dip sos", 20.0)
            ]
        }
        
        existing_prods = execute_query("SELECT id, urun_adi FROM Urunler") or []
        existing_prod_names = {p['urun_adi'].strip().lower(): p['id'] for p in existing_prods}
        
        for cat_name, prod_list in products_data.items():
            cat_id = cat_map.get(cat_name)
            if not cat_id:
                continue
            for pname, pdesc, pprice in prod_list:
                key = pname.strip().lower()
                if key in existing_prod_names:
                    pid = existing_prod_names[key]
                    execute_non_query(
                        "UPDATE Urunler SET kategori_id = ?, aciklama = ?, fiyat = ?, stok_miktari = 100, aktif_mi = 1 WHERE id = ?",
                        (cat_id, pdesc, pprice, pid)
                    )
                    print(f"Ürün güncellendi: {pname} -> Kategori {cat_name} (ID: {pid})")
                else:
                    new_pid = execute_non_query(
                        "INSERT INTO Urunler (kategori_id, urun_adi, aciklama, fiyat, gorsel_url, stok_miktari, aktif_mi) VALUES (?, ?, ?, ?, ?, ?, 1)",
                        (cat_id, pname, pdesc, pprice, "", 100)
                    )
                    print(f"Yeni ürün eklendi: {pname} -> Kategori {cat_name} (ID: {new_pid})")

    print("=== MENÜ VE VERİTABANI GÜNCELLEMESİ BAŞARIYLA TAMAMLANDI ===")

if __name__ == "__main__":
    run_enrichment()
