from app.database import execute_query, execute_non_query, db_transaction

def fix_duplicates():
    print("=== DÜPLİKE KATEGORİ TEMİZLEME BAŞLADI ===")
    with db_transaction():
        # 1. Türkçe olan aktif İçecekler kategorisinin ID'sini bul
        target = execute_query("SELECT id FROM Kategoriler WHERE kategori_adi = 'İçecekler'", fetch_one=True)
        old_cat = execute_query("SELECT id FROM Kategoriler WHERE kategori_adi = 'Icecekler'", fetch_one=True)
        
        if target and old_cat:
            target_id = target['id']
            old_id = old_cat['id']
            print(f"Hedef İçecekler ID: {target_id}, Eski Icecekler ID: {old_id}")
            
            # Eski kategorideki ürünleri yeni kategoriye aktar
            execute_non_query("UPDATE Urunler SET kategori_id = ? WHERE kategori_id = ?", (target_id, old_id))
            print("Ürünler yeni İçecekler kategorisine aktarıldı.")
            
            # Eski kategoriyi sil
            execute_non_query("DELETE FROM Kategoriler WHERE id = ?", (old_id,))
            print(f"Eski Icecekler (ID: {old_id}) kategorisi silindi.")
        else:
            print("Düplike kategori bulunamadı veya işlem önceden yapılmış.")

if __name__ == "__main__":
    fix_duplicates()
