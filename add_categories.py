from app.database import execute_query, execute_non_query

def main():
    try:
        cats = execute_query("SELECT * FROM Kategoriler")
        print("Mevcut Kategoriler:", cats)
        existing = [c['kategori_adi'].lower() for c in (cats or [])]
        
        new_cats = ['Aperatifler', 'Soslar']
        for name in new_cats:
            if name.lower() not in existing:
                cat_id = execute_non_query("INSERT INTO Kategoriler (kategori_adi, aktif_mi) VALUES (?, 1)", (name,))
                print(f"Eklendi: {name} (ID: {cat_id})")
                
                # Örnek ürünler de ekleyelim ki boş görünmesin
                if name == 'Aperatifler':
                    execute_non_query(
                        "INSERT INTO Urunler (kategori_id, urun_adi, aciklama, fiyat, gorsel_url, stok_miktari, aktif_mi) VALUES (?, ?, ?, ?, ?, ?, 1)",
                        (cat_id, "Patates Kızartması", "Çıtır baharatlı patates kızartması", 65.0, "", 100)
                    )
                    execute_non_query(
                        "INSERT INTO Urunler (kategori_id, urun_adi, aciklama, fiyat, gorsel_url, stok_miktari, aktif_mi) VALUES (?, ?, ?, ?, ?, ?, 1)",
                        (cat_id, "Soğan Halkası (8li)", "Çıtır paneli soğan halkaları", 55.0, "", 100)
                    )
                elif name == 'Soslar':
                    execute_non_query(
                        "INSERT INTO Urunler (kategori_id, urun_adi, aciklama, fiyat, gorsel_url, stok_miktari, aktif_mi) VALUES (?, ?, ?, ?, ?, ?, 1)",
                        (cat_id, "Sarımsaklı Mayonez", "Özel ev yapımı sarımsaklı sos", 15.0, "", 100)
                    )
                    execute_non_query(
                        "INSERT INTO Urunler (kategori_id, urun_adi, aciklama, fiyat, gorsel_url, stok_miktari, aktif_mi) VALUES (?, ?, ?, ?, ?, ?, 1)",
                        (cat_id, "Barbekü Sos", "Tütsülenmiş enfes barbekü sosu", 15.0, "", 100)
                    )
            else:
                print(f"Zaten var: {name}")

        print("Güncel Kategoriler:", execute_query("SELECT * FROM Kategoriler"))
    except Exception as e:
        print("Hata oluştu:", str(e))

if __name__ == "__main__":
    main()
