# list_menu.py
from app.database import execute_query

def listele_menu():
    sql = """
    SELECT k.kategori_adi, u.id, u.urun_adi, u.fiyat, u.aciklama
    FROM Urunler u
    JOIN Kategoriler k ON u.kategori_id = k.id
    WHERE k.aktif_mi = 1 AND u.aktif_mi = 1
    ORDER BY k.id ASC, u.id ASC;
    """
    urunler = execute_query(sql) or []
    
    suanki_kategori = ""
    toplam = 0
    for u in urunler:
        toplam += 1
        if u['kategori_adi'] != suanki_kategori:
            suanki_kategori = u['kategori_adi']
            print(f"\n📁 === {suanki_kategori.upper()} ===")
        print(f"  └─ [{u['id']}] {u['urun_adi']} - {u['fiyat']} TL ({u['aciklama']})")
    
    print(f"\n✅ Toplam Aktif Ürün Sayısı: {toplam}")

if __name__ == "__main__":
    listele_menu()
