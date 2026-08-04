import os
import shutil
from app.database import execute_non_query, db_transaction

artifact_dir = r"C:\Users\emre\.gemini\antigravity-ide\brain\4bef9a3d-27a2-454a-b1d4-0a4cf0282dc5"
target_dir = r"c:\Users\emre\Desktop\QR odeme\static\img\kategoriler"

os.makedirs(target_dir, exist_ok=True)

# Geliştirilen resmi hedef isimle eşleştirme
mapping = {
    'Çorbalar': ('cat_corbalar_1785490987010.png', 'corbalar.png'),
    'Pizzalar': ('cat_pizzalar_1785490998230.png', 'pizzalar.png'),
    'Burgerler': ('cat_burgerler_1785491011009.png', 'burgerler.png'),
    'Salatalar': ('cat_salatalar_1785491023896.png', 'salatalar.png'),
    'Tatlılar': ('cat_tatlilar_1785491036987.png', 'tatlilar.png'),
    'İçecekler': ('cat_icecekler_1785491049658.png', 'icecekler.png'),
    'Aperatifler': ('cat_aperatifler_1785491062498.png', 'aperatifler.png'),
    'Soslar': ('cat_soslar_1785491076403.png', 'soslar.png')
}

with db_transaction():
    for cat_name, (src_name, dst_name) in mapping.items():
        src_path = os.path.join(artifact_dir, src_name)
        dst_path = os.path.join(target_dir, dst_name)
        
        if os.path.exists(src_path):
            shutil.copy2(src_path, dst_path)
            gorsel_url = f"/static/img/kategoriler/{dst_name}"
            execute_non_query("UPDATE Kategoriler SET gorsel_url = ? WHERE kategori_adi = ?", (gorsel_url, cat_name))
            print(f"Kategori '{cat_name}' görseli kopyalandı ve veritabanı güncellendi: {gorsel_url}")
        else:
            print(f"Kaynak görsel bulunamadı: {src_path}")

print("=== KATEGORİ GÖRSELLERİ AKTARIMI TAMAMLANDI ===")
