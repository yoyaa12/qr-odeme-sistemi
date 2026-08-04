from app.database import execute_query, execute_non_query, db_transaction

def nuke_old_icecekler():
    print("=== NUKING OLD ICECEKLE KATEGORISI ===")
    with db_transaction():
        all_cats = execute_query("SELECT id, kategori_adi, aktif_mi FROM Kategoriler")
        print("Tüm Kategoriler:", all_cats)
        
        target_tr = None
        for c in (all_cats or []):
            name = c['kategori_adi'].strip()
            if name == 'İçecekler':
                target_tr = c['id']
                
        for c in (all_cats or []):
            name = c['kategori_adi'].strip()
            cid = c['id']
            if name == 'Icecekler' or (name.lower() == 'icecekler' and cid != target_tr):
                print(f"Eski Icecekler kategorisi bulundu ID: {cid}, Siliniyor...")
                if target_tr:
                    execute_non_query("UPDATE Urunler SET kategori_id = ? WHERE kategori_id = ?", (target_tr, cid))
                execute_non_query("DELETE FROM Kategoriler WHERE id = ?", (cid,))
                print(f"ID {cid} başarıyla silindi.")

if __name__ == "__main__":
    nuke_old_icecekler()
