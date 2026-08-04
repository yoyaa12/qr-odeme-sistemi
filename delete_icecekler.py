from app.database import execute_query, execute_non_query, db_transaction

def remove_old_icecekler():
    print("=== ESKİ ICECEKLER KATEGORİSİ SİLİNİYOR ===")
    with db_transaction():
        # Active Türkçe İçecekler ID
        target = execute_query("SELECT id FROM Kategoriler WHERE kategori_adi = 'İçecekler'", fetch_one=True)
        if target:
            target_id = target['id']
            # Move any product attached to old 'Icecekler'
            execute_non_query("UPDATE Urunler SET kategori_id = ? WHERE kategori_id IN (SELECT id FROM Kategoriler WHERE kategori_adi = 'Icecekler')", (target_id,))
            # Delete old 'Icecekler'
            execute_non_query("DELETE FROM Kategoriler WHERE kategori_adi = 'Icecekler'")
            print(f"Eski 'Icecekler' kategorisi veritabanından tamamen kaldırıldı.")

if __name__ == "__main__":
    remove_old_icecekler()
